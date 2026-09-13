"""Validated millimeter-based project settings shared by every entrypoint."""

from math import sqrt
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    width_mm: float = Field(default=180, ge=30, le=1500)
    height_mm: float = Field(default=180, ge=30, le=1500)
    base_mm: float = Field(default=2.4, ge=1.2, le=12)
    relief_mm: float = Field(default=0.8, ge=0.4, le=8)
    frame: bool = True
    frame_width_mm: float = Field(default=4, ge=1, le=30)
    frame_height_mm: float = Field(default=1.6, ge=0.4, le=12)
    frame_profile: Literal["flat", "rounded"] = "flat"
    corner_radius_mm: float = Field(default=0, ge=0, le=100)
    margin_mm: float = Field(default=3, ge=0, le=30)
    crop_to_artwork: bool = True
    threshold: int = Field(default=128, ge=1, le=254)
    foreground: Literal["auto", "dark", "light"] = "auto"
    invert: bool = False
    detail: Literal["draft", "balanced", "fine"] = "balanced"
    min_area_mm2: float = Field(default=0.6, ge=0, le=20)
    layout: Literal["plaque", "tiles", "puzzle"] = "plaque"
    columns: int = Field(default=0, ge=0, le=12)
    rows: int = Field(default=0, ge=0, le=12)
    clearance_mm: float = Field(default=0.25, ge=0, le=1)
    bed_width_mm: float = Field(default=230, ge=60, le=256)
    bed_height_mm: float = Field(default=230, ge=60, le=256)
    hanging: Literal["none", "loops", "keyholes"] = "none"
    background_color: str = Field(default="#fcfcfa", pattern=r"^#[0-9a-fA-F]{6}$")
    artwork_color: str = Field(default="#252b28", pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def compatible_dimensions(self) -> Self:
        if self.corner_radius_mm > min(self.width_mm, self.height_mm) / 2:
            raise ValueError("Corner radius cannot exceed half the shorter side.")
        inset = self.artwork_inset
        if min(self.width_mm, self.height_mm) - 2 * inset < 10:
            raise ValueError("Frame and margin must leave at least 10 mm for the artwork.")
        if bool(self.columns) != bool(self.rows):
            raise ValueError("Set both rows and columns, or use 0 for both to split automatically.")
        if self.columns * self.rows > 64:
            raise ValueError("A project can contain at most 64 pieces.")
        if self.layout == "plaque" and (self.columns > 1 or self.rows > 1):
            raise ValueError("Choose Tiles or Puzzle to use multiple rows or columns.")
        if self.hanging == "keyholes" and self.base_mm < 5:
            raise ValueError("Rear keyholes need a backing at least 5 mm thick.")
        return self

    @property
    def artwork_inset(self) -> float:
        inset = (self.frame_width_mm if self.frame else 0) + self.margin_mm
        # Keep the whole artwork rectangle inside rounded corners, without clipping it.
        return inset + max(0, self.corner_radius_mm - inset) * (1 - 1 / sqrt(2))

    @property
    def trace_resolution(self) -> int:
        return {"draft": 384, "balanced": 768, "fine": 1280}[self.detail]

    @property
    def simplify_mm(self) -> float:
        return {"draft": 0.3, "balanced": 0.12, "fine": 0.05}[self.detail]
