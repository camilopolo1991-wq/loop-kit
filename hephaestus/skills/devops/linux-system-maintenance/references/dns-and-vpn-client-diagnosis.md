# Diagnosing DNS and zero-trust/VPN clients on Linux

For a VPN or zero-trust client (Twingate, Tailscale, WARP, corporate agents) that
will not start, will not authenticate, or "is not working", and for host-level DNS
failures generally. The client is usually the victim, not the cause: these clients
rewrite link DNS, so anything already wrong with resolution surfaces as a client
fault.

## Order of diagnosis

Work bottom-up. Each layer's answer decides whether the next one is even relevant.

1. Is the service running at all, and is the unit enabled?

       systemctl status <svc> --no-pager
       systemctl is-active <svc>; systemctl is-enabled <svc>
       <client> status

   `activating` plus a CLI status of not-running is a restart loop, not a
   start-up in progress. Read it as failing, and note that `enabled` means the
   loop returns after reboot.

2. Read the journal for the state machine, never the CLI status word alone. One
   CLI word covers several distinct failures:

       journalctl -u <svc> --no-pager -n 40 | grep -E "ERROR|WARNING|State:|netmgr|stub|dns"

   Follow the last `State:` transitions. `Offline -> Authenticating -> Error ->
   Offline` on a ~15s cycle is a network-reachability failure during handshake.
   An abort before any `Authenticating` is a local link/config failure and
   authentication is not the problem yet.

3. Layer 3 vs name resolution. Prove raw connectivity works before blaming DNS:

       ip route; ip -br addr; ip -br link
       ping -c2 -W2 1.1.1.1
       curl -s -o /dev/null -w '%{http_code}\n' https://1.1.1.1

   Packets fine plus names failing narrows it to resolution. A missing tun/utun/
   sdwan interface in `ip -br link` means the client never came up; its presence
   means it did and the fault is later.

4. UDP-vs-TCP control pair on port 53. This is the highest-value single test:

       for s in 1.1.1.1 8.8.8.8 9.9.9.9 <link-dns> 127.0.0.53; do
         printf 'UDP @%s: ' "$s"; timeout 6 dig +short +time=2 +tries=1 @$s example.com | tr '\n' ' '; echo
       done
       dig +tcp +short +time=3 @1.1.1.1 example.com    # control

   If TCP answers and UDP times out for EVERY address including public ones, the
   blocker is transport interception (hypervisor NAT DNS proxy, host firewall,
   captive network), not resolver choice. Changing nameservers cannot fix it and
   recommending a different resolver wastes a round trip.

5. Only then look at which resolvers are on the link and who put them there.

## Finding the source of link DNS

Never assume a static profile. Compare the profile against what DHCP delivered:

    resolvectl status <dev>
    nmcli -f ipv4.dns,ipv4.dns-search,ipv4.ignore-auto-dns,ipv4.method con show <con>
    nmcli -f DHCP4 dev show <dev> | grep -i -E "domain_name_server|domain_name|dhcp_server"

`ipv4.dns: --` while `resolvectl` shows a populated list means the addresses came
from DHCP, so clearing `ipv4.dns` is a no-op. `dhcp_server_identifier` names the
actual source.

### Suppressing DHCP-supplied DNS (NetworkManager)

    sudo nmcli con mod <con> ipv4.ignore-auto-dns yes
    sudo nmcli con mod <con> ipv4.dns "1.1.1.1 9.9.9.9"
    sudo nmcli con down <con> && sudo nmcli con up <con>
    resolvectl status <dev>

Gate on `resolvectl` showing only the intended addresses before moving on.

If the unwanted entries survive a profile change, they are written elsewhere:
grep `/etc/netplan/`, `/etc/systemd/resolved.conf`, `/etc/systemd/resolved.conf.d/`
and `/etc/NetworkManager/` for the addresses. Netplan files are mode 0600, so a
plain read fails and the file must be surfaced to the user rather than edited
blind.

## Virtualised guests inheriting the host's resolvers

A VirtualBox NAT guest (address `10.0.2.15/24`, gateway `10.0.2.2`,
`dhcp_server_identifier = 10.0.2.2`) is handed the HOST's resolver list by the NAT
engine, and the NAT engine also proxies guest UDP 53 through the host resolver.
When the host runs a VPN client, the guest inherits that client's stub resolvers
and its UDP 53 dies with them. One root cause, two symptoms: a VPN client in the
guest that aborts on link state, and host-wide UDP 53 timeouts.

Fix at the host, VM powered off:

    VBoxManage modifyvm <vm> --natdnshostresolver1 off
    VBoxManage modifyvm <vm> --natdnsproxy1 off

or move the VM to bridged networking so it stops inheriting host DNS entirely.

Before any of that, settle the design question with the user: is the guest meant
to be its own enrolled device, or to ride the host's tunnel? If the latter,
`systemctl disable --now <svc>` in the guest is the fix and every config change
inside it is wasted work.

## ICMP answers but TCP times out: connected and NOT authorized

This pair is the signature of a step-up authentication gate, not of a firewall, a
dead host or a broken tunnel, and it is worth recognising on sight because it
sends diagnosis in completely the wrong direction:

    ping <tunnel-ip>            -> replies normally
    /dev/tcp/<tunnel-ip>/22     -> connection timed out
    tunnel iface in ip -br link -> present, with an address
    <client> status             -> online

The client is up, so ICMP passes, while the resource itself is gated and the
client drops its TCP packets. `online` from the status verb describes the CLIENT,
never the resource. Read the resource list and its auth state before anything
else, and before concluding a host is unreachable.

### Minting the login URL from the agent shell

The user does not need a working terminal, browser or desktop on the affected
machine to authenticate. The auth verb usually requires the resource NAME as an
argument — a bare call fails with "resource must be specified" — so list first and
pass the name verbatim and quoted, spaces included:

    <client> resources
    <client> auth "<Resource Name>" > /tmp/auth.txt 2>&1
    grep -o 'https://[^ ]*' /tmp/auth.txt | head -1 > ~/auth_url.txt

Print it for the user to open on whatever machine has a usable browser, and save
it to a file as a second route. **Never retype, reflow or reformat the URL**: it
carries a long signed `state` parameter, one altered character invalidates it, and
a copy mangled in transit is indistinguishable from an expired one. Say it is
short-lived and that regenerating costs nothing.

Authentication completed on a different device still unlocks this one — the grant
is recorded server-side against the client, not the browser. Verify by re-reading
the resource list (expect an explicit expiry per resource) and then by the real
protocol; the status verb will not show the change.

Where a browser does exist locally but exits immediately with "no DISPLAY
 environment variable specified", the session is Wayland: check
`/run/user/$(id -u)/wayland-0` and pass `WAYLAND_DISPLAY=wayland-0` plus
`XDG_RUNTIME_DIR` rather than guessing `DISPLAY=:0`, which is dead on such hosts.

## A port behind the tunnel times out while others stay open

When one service through a zero-trust tunnel stops answering and others on the
same host keep working, the client's own per-resource authorization state is the
first thing to read — before any firewall theory and before messaging whoever
administers the tunnel:

    twingate resources        # or the vendor equivalent resource/route listing

These clients authorize each resource separately and expire them separately. A
resource in `Pending` (or expired) state has its packets dropped by the client,
which presents as `Connection timed out`, identical to a firewall drop and
distinct from the `Connection refused` a dead daemon gives. Two resources sharing
one address can therefore disagree: the web resource answers while the SSH
resource on the same IP is silent.

Do not reason from timed-out-versus-refused to "a firewall or policy changed".
That inference is sound only once the client reports the resource authorized. Pair
the probe with a control on the same tunnel address that must succeed, and with
the host's public address to separate tunnel from host:

    for p in 22 443; do timeout 12 bash -c "cat < /dev/null > /dev/tcp/<tunnel-ip>/$p" \
      && echo "  $p OPEN" || echo "  $p filtered"; done
    ip route get <tunnel-ip>      # must leave via the tunnel interface
    ip route get <public-ip>      # leaves via the physical NIC, so it is a different path

A reboot, a client restart, or a re-auth commonly leaves some resources Pending
while others come back, so recheck the resource list after either before
concluding anything about the remote host. Never draft a message asking an
administrator whether a policy changed until the resource list has been read: the
answer is usually on this side.

## Pitfalls

- `ipv4.ignore-auto-dns no` means ACCEPT the DHCP-supplied DNS. Setting it to `no`
  to "stop ignoring the real DNS" does the opposite of clearing a poisoned list;
  `yes` plus an explicit `ipv4.dns` is what suppresses DHCP.
- Clearing `ipv4.dns` removes only STATIC entries. Check `nmcli -f DHCP4 dev show`
  first, or you will clear an already-empty field and report a fix that changed
  nothing.
- A client aborting with a message about detecting its own stub resolvers is
  reacting to addresses already on the link, usually left by a previous run or by
  another instance of the same client upstream. Clear the link first; re-running
  the vendor's `setup` command rewrites tenant/account config and cannot fix a
  link-state abort.
- An empty-token or missing-credentials warning in the same log is downstream
  noise when the client aborted before reaching `Authenticating`. Do not chase
  authentication until the client gets that far.
- Pair every zero/timeout result with a control that must succeed (same query over
  TCP, a second resolver, a known-good host). A DNS query that returns nothing has
  two explanations and only one of them is the client's fault.
- Do not recommend a DNS-over-TLS workaround without first control-testing that
  outbound TCP 853 is reachable. Label unverified workarounds as unproven and give
  the cost; an untested config change to name resolution is worse than a known
  blocker.
- Enable the unit for boot only after the client has reached a healthy state once.
  Enabling during diagnosis makes a restart loop persistent across reboot.
