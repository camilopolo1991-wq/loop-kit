#!/usr/bin/env python3
"""Prove whether a cutoff scheme can tie against an attainable weighted total.

Per-item weights of 1 / 0.5 / 0 put the weighted total on a lattice of step 0.5, so a
cutoff written as a fraction of N can land exactly on an attainable value -- making one
item's grading decide the band. Run this BEFORE proposing any offset: the intuitive
0.25 is not tie-free at odd N.

Every scheme is reported alongside the UNOFFSET scheme as a positive control. A control
of 0 collisions means the enumerator is broken and no result below is trustworthy.

Usage:  python3 cutoff_tie_check.py [--min-n 2] [--max-n 20]
"""
import argparse

WEIGHTS = (1.0, 0.5, 0.0)
EPS = 1e-9


def attainable(n):
    """Every weighted total reachable with n items under WEIGHTS."""
    return {ev + pa * 0.5 for ev in range(n + 1) for pa in range(n + 1 - ev)}


def collisions(scheme, lo, hi):
    out = []
    for n in range(lo, hi + 1):
        totals = attainable(n)
        for name, cut in scheme(n).items():
            if any(abs(t - cut) < EPS for t in totals):
                out.append((n, name, cut))
    return out


SCHEMES = {
    "unoffset (CONTROL, must collide)":
        lambda n: {"exceptional": n, "strong": n * 0.75, "adequate": n * 0.5},
    "all -0.25":
        lambda n: {"exceptional": n - 0.25, "strong": n * 0.75 - 0.25,
                   "adequate": n * 0.5 - 0.25},
    "adequate/exceptional -0.25, strong -0.125":
        lambda n: {"exceptional": n - 0.25, "strong": n * 0.75 - 0.125,
                   "adequate": n * 0.5 - 0.25},
    "all -0.125":
        lambda n: {"exceptional": n - 0.125, "strong": n * 0.75 - 0.125,
                   "adequate": n * 0.5 - 0.125},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=2)
    ap.add_argument("--max-n", type=int, default=20)
    a = ap.parse_args()

    control = collisions(SCHEMES["unoffset (CONTROL, must collide)"], a.min_n, a.max_n)
    print(f"N range {a.min_n}..{a.max_n}, lattice step 0.5\n")
    for name, fn in SCHEMES.items():
        c = collisions(fn, a.min_n, a.max_n)
        flag = "" if c else "  <- tie-free"
        print(f"  {name:44} {len(c):3} collisions{flag}")
        for n, cut_name, cut in c[:3]:
            print(f"      N={n} {cut_name} cutoff {cut} is attainable")
    print()
    if not control:
        print("CONTROL FAILED: the unoffset scheme reported no collisions, so the")
        print("enumerator cannot detect one. Every zero above is meaningless.")
        raise SystemExit(2)
    print(f"control ok: unoffset scheme collides {len(control)} times, so a reported")
    print("zero above is a real absence rather than a broken check.")


if __name__ == "__main__":
    main()
