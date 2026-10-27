#!/usr/bin/env python3
"""Shared geographical configuration for CodeBlue downloads."""

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Geographical domain in degrees."""

    west: float
    east: float
    south: float
    north: float
    padding: float = 1.0

    def __post_init__(self):
        if not -180 <= self.west < self.east <= 180:
            raise ValueError("Invalid longitude limits.")

        if not -90 <= self.south < self.north <= 90:
            raise ValueError("Invalid latitude limits.")

        if self.padding < 0:
            raise ValueError("Padding must be non-negative.")

        if self.south - self.padding < -90:
            raise ValueError("Southern limit exceeds -90 degrees.")

        if self.north + self.padding > 90:
            raise ValueError("Northern limit exceeds 90 degrees.")

        if self.west - self.padding < -180:
            raise ValueError("Western limit exceeds -180 degrees.")

        if self.east + self.padding > 180:
            raise ValueError("Eastern limit exceeds 180 degrees.")

    @property
    def bounds(self):
        """Return padded (west, east, south, north)."""

        return (
            self.west - self.padding,
            self.east + self.padding,
            self.south - self.padding,
            self.north + self.padding,
        )


def add_region_arguments(parser):
    """Add geographical arguments to an argparse parser."""

    parser.add_argument("--west", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--north", type=float, required=True)

    parser.add_argument(
        "--padding",
        type=float,
        default=1.0,
        help="Additional geographical margin in degrees (default: 1).",
    )


def get_region(args):
    """Build and validate a Region from parsed arguments."""

    return Region(
        west=args.west,
        east=args.east,
        south=args.south,
        north=args.north,
        padding=args.padding,
    )
