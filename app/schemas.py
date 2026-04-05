"""Pydantic models for POST /api/analyze (teaching API)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GlassType = Literal["AN", "HS", "FT"]
Construction = Literal["monolithic", "laminated"]
SupportFamily = Literal[
    "monolithic_four_sides",
    "laminated_four_sides",
    "monolithic_three_sides",
    "laminated_three_sides",
    "monolithic_two_sides",
    "laminated_two_sides",
    "monolithic_one_side",
    "laminated_one_side",
]
PanelCase = Literal[
    "single_monolithic",
    "double_ig_momo",
    "double_ig_molg",
    "triple_ig",
]
Duration = Literal["short", "long"]


class WindParams(BaseModel):
    """Reference wind for logarithmic profile (same form as wind-data.ch)."""

    v1_m_s: float = Field(..., description="Reference wind speed at height h1 (m/s)")
    h1_m: float = Field(10.0, description="Reference height (m)")
    z0_m: float = Field(0.4, description="Roughness length (m), terrain dependent")
    air_density_kg_m3: float = Field(1.225, description="For dynamic pressure q = 0.5 * rho * v^2")
    pressure_factor: float = Field(
        1.0,
        description="Multiplies dynamic pressure to obtain design lateral pressure (workshop default)",
    )


class LiteInput(BaseModel):
    nominal_key: str | None = Field(
        None,
        description="Table 4 key e.g. '6', '8'; if null, API searches minimum nominal",
    )
    glass: GlassType = "AN"
    construction: Construction = "monolithic"


class PanelInput(BaseModel):
    id: str = Field(..., description="Stable id from Grasshopper tree path")
    width_m: float = Field(..., gt=0, description="Panel width (m), mapped to short edge if smaller")
    height_m: float = Field(..., gt=0, description="Panel height (m)")
    elevation_m: float = Field(
        0.0,
        description="Height of panel centroid above ground for wind profile (m)",
    )
    case: PanelCase = "single_monolithic"
    support_family: SupportFamily = "monolithic_four_sides"
    duration: Duration = "short"
    lites: list[LiteInput] = Field(
        default_factory=lambda: [LiteInput()],
        min_length=1,
        max_length=3,
    )


class AnalyzeRequest(BaseModel):
    wind: WindParams = Field(default_factory=WindParams)
    panels: list[PanelInput] = Field(..., min_length=1)
    session_id: str | None = Field(None, description="Optional key for multi-tab in-memory store")


class WindDerived(BaseModel):
    v_at_panel_m_s: float
    dynamic_pressure_kpa: float
    design_load_kpa: float


class OracleResult(BaseModel):
    governing_LR_kpa: float
    acceptable: bool
    details: dict[str, Any] = Field(default_factory=dict)
    minimum_nominal_key: str | None = None


class MLResult(BaseModel):
    predicted_nominal_key: str | None = None
    predicted_governing_LR_kpa: float | None = None
    ml_backend: str | None = None
    ml_available: bool = False
    feature_importance: dict[str, float] | None = None


class PanelResult(BaseModel):
    id: str
    short_m: float
    long_m: float
    wind: WindDerived
    oracle: OracleResult
    ml: MLResult


class AnalyzeResponse(BaseModel):
    ok: bool = True
    disclaimer: str = "Workshop / teaching only. Not a substitute for licensed standards or site-specific wind engineering."
    panels: list[PanelResult]
    raw_request_echo: dict[str, Any] | None = None


class LastResultStore(BaseModel):
    """Shape for GET /api/last (in-memory demo)."""

    request: dict[str, Any]
    response: dict[str, Any]
