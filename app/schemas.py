"""Pydantic models for POST /api/analyze (teaching API)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.panel_geometry import derive_short_long_area

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

    v1_m_s: float = Field(17.56, description="Reference wind speed at height h1 (m/s)")
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
    width_m: float | None = Field(
        None,
        description="Panel width (m); required if not sending vertices",
    )
    height_m: float | None = Field(
        None,
        description="Panel height (m); required if not sending vertices",
    )
    use_explicit_dimensions: bool = Field(
        False,
        description="If true, use width_m/height_m and ignore vertices for sizing",
    )
    n_edges: Literal[3, 4] | None = Field(None, description="Triangle or quad vertex count")
    vertices_m: list[list[float]] | None = Field(
        None,
        description="Polygon vertices in order (m), length must equal n_edges",
    )
    edge_lengths_m: list[float] | None = Field(None, description="Optional validation against vertices")
    normal: list[float] | None = Field(None, description="Optional unit outward normal")
    area_m2: float | None = Field(None, description="Optional validation against computed area")
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
    resolved_from_geometry: bool = Field(
        False,
        description="Set by server when dimensions were derived from vertices",
    )

    @model_validator(mode="after")
    def resolve_dimensions(self) -> PanelInput:
        if self.use_explicit_dimensions:
            if self.width_m is None or self.height_m is None:
                raise ValueError("use_explicit_dimensions requires width_m and height_m")
            if self.width_m <= 0 or self.height_m <= 0:
                raise ValueError("width_m and height_m must be positive")
            return self

        if self.vertices_m is not None and self.n_edges is not None:
            short_m, long_m, _area, _n = derive_short_long_area(
                self.n_edges,
                self.vertices_m,
                self.normal,
                self.edge_lengths_m,
                self.area_m2,
            )
            self.width_m = short_m
            self.height_m = long_m
            self.resolved_from_geometry = True
            return self

        if self.width_m is not None and self.height_m is not None:
            if self.width_m <= 0 or self.height_m <= 0:
                raise ValueError("width_m and height_m must be positive")
            return self

        raise ValueError(
            "Provide either (width_m and height_m) or (n_edges and vertices_m), "
            "or set use_explicit_dimensions with explicit sizes",
        )

    def as_sized(self) -> PanelInput:
        """Return self after validation (width_m/height_m always set)."""
        assert self.width_m is not None and self.height_m is not None
        return self


class AnalyzeRequest(BaseModel):
    wind: WindParams = Field(default_factory=WindParams)
    panels: list[PanelInput] | None = Field(
        None,
        description="If omitted, session_id must refer to a session with uploaded panels",
    )
    session_id: str | None = Field(None, description="Optional key for multi-tab in-memory store")


class SessionUploadRequest(BaseModel):
    session_id: str | None = Field(
        None,
        description="If omitted, server creates a new id (returned in response). Wind is not sent from Grasshopper; set wind in the web app.",
    )
    wind: WindParams | None = Field(
        None,
        description="Optional; usually set via PUT /api/session/{id}/wind from the dashboard, not from GH.",
    )
    panels: list[PanelInput] = Field(..., min_length=1)


class SessionUploadResponse(BaseModel):
    ok: bool = True
    session_id: str
    panel_count: int
    resolved_preview: list[dict[str, Any]]


class SessionCalculateRequest(BaseModel):
    wind: WindParams | None = None
    algorithms: list[str] | None = Field(
        None,
        description="Strategy IDs to run (e.g. ['knn_k7','ridge','svr']). None = all registered.",
    )


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
    strategy_id: str | None = None
    strategy_label: str | None = None
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
    ml_by_strategy: dict[str, MLResult] = Field(
        default_factory=dict,
        description="All k-NN strategies from ml_registry.json for comparison charts",
    )


class AnalyzeResponse(BaseModel):
    ok: bool = True
    disclaimer: str = "Workshop / teaching only. Not a substitute for licensed standards or site-specific wind engineering."
    panels: list[PanelResult]
    raw_request_echo: dict[str, Any] | None = None


class ClusterGroup(BaseModel):
    cluster_index: int
    color_hex: str
    nominal_key: str | None = None
    thickness_mm_min: float | None = None
    panel_ids: list[str]


class SessionResultsResponse(BaseModel):
    ok: bool = True
    session_id: str
    wind: dict[str, Any]
    panels: list[dict[str, Any]]
    clusters: list[ClusterGroup]
    analyze: dict[str, Any] | None = None


class SessionGeometryResponse(BaseModel):
    ok: bool = True
    session_id: str
    panel_count: int
    panels: list[dict[str, Any]]


class LastResultStore(BaseModel):
    """Shape for GET /api/last (in-memory demo)."""

    request: dict[str, Any]
    response: dict[str, Any]
