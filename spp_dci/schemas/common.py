"""Common DCI schema types."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Identifier(BaseModel):
    """DCI Identifier schema - unique identification credentials."""

    model_config = ConfigDict(populate_by_name=True)

    identifier_type: str = Field(
        ...,
        description="Type of identifier (UIN, BRN, MRN, DRN, or namespace URI)",
    )
    identifier_value: str = Field(
        ...,
        description="The actual identifier value",
    )


class Name(BaseModel):
    """DCI Name schema - structured name representation."""

    model_config = ConfigDict(populate_by_name=True)

    surname: str | None = Field(None, description="Family/last name")
    given_name: str | None = Field(None, description="First name")
    second_name: str | None = Field(None, description="Middle name")
    maiden_name: str | None = Field(None, description="Maiden name if applicable")
    prefix: str | None = Field(None, description="Name prefix (Dr., Mr., etc.)")
    suffix: str | None = Field(None, description="Name suffix (Jr., Sr., etc.)")


class GeoCoordinates(BaseModel):
    """DCI GeoCoordinates - WGS 84 latitude/longitude."""

    model_config = ConfigDict(populate_by_name=True)

    latitude: float = Field(..., description="Latitude value")
    longitude: float = Field(..., description="Longitude value")


class GeoLocationBounds(BaseModel):
    """Geographic bounds with northeast and southwest corners."""

    model_config = ConfigDict(populate_by_name=True)

    northeast: GeoCoordinates | None = None
    southwest: GeoCoordinates | None = None


class GeoLocationGeometry(BaseModel):
    """Geometry for a geographic location."""

    model_config = ConfigDict(populate_by_name=True)

    bounds: GeoLocationBounds | None = None
    location: GeoCoordinates | None = None


class PlusCode(BaseModel):
    """Plus Code geographic reference."""

    model_config = ConfigDict(populate_by_name=True)

    global_code: str | None = Field(None, description="Plus code reference")
    geometry: GeoLocationGeometry | None = None


class GeoLocation(BaseModel):
    """DCI GeoLocation - Plus Codes with geometry."""

    model_config = ConfigDict(populate_by_name=True)

    plus_code: PlusCode | None = None


class Address(BaseModel):
    """DCI Address schema - structured address representation."""

    model_config = ConfigDict(populate_by_name=True)

    address_line_1: str | None = Field(None, description="First address line")
    address_line_2: str | None = Field(None, description="Second address line")
    locality: str | None = Field(None, description="City or locality")
    sub_region_code: str | None = Field(None, description="District or sub-regional code")
    region_code: str | None = Field(None, description="State, province, or region")
    postal_code: str | None = Field(None, description="Zip/postal code")
    country_code: str | None = Field(None, description="Country identifier")
    geo_location: GeoLocation | None = Field(None, description="Geographic location")


class Place(BaseModel):
    """DCI Place - named geographic location with hierarchy."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(None, description="Place name")
    address_line: str | None = Field(None, description="Full mailing address")
    geo: GeoCoordinates | None = Field(None, description="Location coordinates")
    contained_in_place: Optional["Place"] = Field(None, description="Larger place containing this place")
    contains_place: list["Place"] | None = Field(None, description="Smaller places within this place")


class AdditionalAttribute(BaseModel):
    """DCI AdditionalAttribute - custom key-value pair."""

    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(..., description="Attribute key")
    value: str = Field(..., description="Attribute value")


class Period(BaseModel):
    """A time period with start and optional end."""

    model_config = ConfigDict(populate_by_name=True)

    start: date | None = Field(None, description="Start date")
    end: date | None = Field(None, description="End date")


# Update forward references
Place.model_rebuild()
