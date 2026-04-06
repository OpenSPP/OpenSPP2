# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for statistics discovery API."""

from pydantic import BaseModel, ConfigDict, Field


class StatisticInfo(BaseModel):
    """Information about a single published statistic."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "total_households",
                    "label": "Total Households",
                    "description": "Total number of households in the area",
                    "format": "count",
                },
            ],
        },
    )

    name: str = Field(..., description="Technical name (e.g., 'total_households')")
    label: str = Field(..., description="Display label (e.g., 'Total Households')")
    description: str | None = Field(default=None, description="Detailed description")
    format: str = Field(..., description="Aggregation format (count, sum, avg, percent, ratio, currency)")
    unit: str | None = Field(default=None, description="Unit of measurement")


class StatisticCategoryInfo(BaseModel):
    """Information about a category of statistics."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "demographics",
                    "name": "Demographics",
                    "icon": "fa-users",
                    "statistics": [
                        {
                            "name": "total_individuals",
                            "label": "Total Individuals",
                            "format": "count",
                        },
                    ],
                },
            ],
        },
    )

    code: str = Field(..., description="Category code (e.g., 'demographics')")
    name: str = Field(..., description="Display name (e.g., 'Demographics')")
    icon: str | None = Field(default=None, description="Font Awesome icon class")
    statistics: list[StatisticInfo] = Field(..., description="Statistics in this category")


class StatisticsListResponse(BaseModel):
    """Response listing all published statistics for a context."""

    categories: list[StatisticCategoryInfo] = Field(..., description="Statistics organized by category")
    total_count: int = Field(..., description="Total number of statistics across all categories")
