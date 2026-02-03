"""DCI constants and enumerations."""

from enum import Enum


class RegistryType(str, Enum):
    """DCI Registry types."""

    SOCIAL_REGISTRY = "SOCIAL_REGISTRY"
    IBR = "IBR"
    CRVS = "CRVS"
    DISABILITY_REGISTRY = "DR"
    FUNCTIONAL_REGISTRY = "FR"


class RegistryEventType(str, Enum):
    """DCI Registry event types."""

    # Common events
    REGISTRATION = "REGISTRATION"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # CRVS events
    BIRTH = "BIRTH"
    DEATH = "DEATH"
    MARRIAGE = "MARRIAGE"
    DIVORCE = "DIVORCE"

    # IBR events
    ENROLLMENT = "ENROLLMENT"
    DISENROLLMENT = "DISENROLLMENT"
    BENEFIT_DISBURSEMENT = "BENEFIT_DISBURSEMENT"


class QueryType(str, Enum):
    """DCI query types for search operations."""

    IDTYPE_VALUE = "idtype-value"
    EXPRESSION = "expression"
    PREDICATE = "predicate"
    GRAPHQL = "graphql"


class RequestStatus(str, Enum):
    """DCI request status codes."""

    RECEIVED = "rcvd"
    PENDING = "pdng"
    SUCCESS = "succ"
    REJECTED = "rjct"


class RegistryRecordType(str, Enum):
    """DCI registry record types."""

    PERSON = "PERSON"
    GROUP = "GROUP"
    BENEFICIARY = "BENEFICIARY"
    FARMER = "FARMER"
    PWD_PERSON = "PWD_PERSON"


class SexCategory(str, Enum):
    """DCI sex category values (ISO 5218)."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class MaritalStatus(str, Enum):
    """DCI marital status codes."""

    SINGLE = "S"
    MARRIED = "M"
    WIDOWED = "W"
    ANNULLED = "A"
    DIVORCED = "D"
    LEGALLY_SEPARATED = "L"
    UNKNOWN = "U"


class IdentifierType(str, Enum):
    """Standard DCI identifier types."""

    UIN = "UIN"  # Unique Identification Number
    BRN = "BRN"  # Birth Registration Number
    MRN = "MRN"  # Marriage Registration Number
    DRN = "DRN"  # Death Registration Number


class FunctionalSeverity(int, Enum):
    """DCI functional severity levels (1-4 scale)."""

    NO_DIFFICULTY = 1
    SOME_DIFFICULTY = 2
    A_LOT_OF_DIFFICULTY = 3
    CANNOT_DO = 4


class DisabilityType(str, Enum):
    """DCI disability/functional limitation types."""

    VISION = "Vision"
    HEARING = "Hearing"
    MOBILITY = "Mobility"
    COGNITION = "Cognition"
    SELF_CARE = "SelfCare"
    COMMUNICATION = "Communication"


class AssistanceUnitEnum(str, Enum):
    """DCI assistance unit types (group_type)."""

    MEMBER = "Member"
    HOUSEHOLD = "Household"
    FAMILY = "Family"


class EmploymentStatusEnum(str, Enum):
    """DCI employment status categories."""

    EMPLOYED = "Employed"
    NOT_EMPLOYED = "Not Employed"
    UNKNOWN = "Unknown"
    PAID_EMPLOYEE = "Paid employment: Employee"
    SELF_EMPLOYED_EMPLOYER = "Self employment: Employers"
    SELF_EMPLOYED_OWN_ACCOUNT = "Self employment: Own-account workers"
    SELF_EMPLOYED_COOPERATIVE = "Self employment: Members of producers' cooperatives"
    SELF_EMPLOYED_FAMILY_WORKER = "Self employment: Contributing family workers"


class OccupationEnum(str, Enum):
    """DCI occupation categories (ISCO-08 based)."""

    ARMED_FORCES = "Armed forces occupation"
    MANAGER = "Manager"
    PROFESSIONAL = "Professional"
    TECHNICIAN = "Technician and associate professional"
    CLERICAL = "Clerical support worker"
    SERVICE_SALES = "Service and sales worker"
    AGRICULTURE = "Skilled agricultural, forestry and fishery worker"
    CRAFT = "Craft and related trades worker"
    OPERATOR = "Plant and machine operator, and assembler"
    ELEMENTARY = "Elementary occupation"


class IncomeLevelEnum(str, Enum):
    """DCI income level categories."""

    LEVEL_1 = "1"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class LanguageCodeEnum(str, Enum):
    """DCI language codes (ISO 639-1)."""

    EN = "en"
    FR = "fr"
    ES = "es"
    AR = "ar"
    PT = "pt"
    ZH = "zh"
    HI = "hi"
    RU = "ru"
    DE = "de"


class EducationCodeEnum(str, Enum):
    """DCI education level codes (ISCED based)."""

    EARLY_CHILDHOOD = "Early childhood education"
    PRIMARY = "Primary education"
    LOWER_SECONDARY = "Lower secondary education"
    UPPER_SECONDARY = "Upper secondary education"
    POST_SECONDARY_NON_TERTIARY = "Post-secondary non-tertiary education"
    SHORT_CYCLE_TERTIARY = "Short-cycle tertiary education"
    BACHELOR = "Bachelor's or equivalent"
    MASTER = "Master's or equivalent"
    DOCTORATE = "Doctorate or equivalent"


class RelationshipTypeEnum(str, Enum):
    """DCI relationship type codes."""

    SELF = "SELF"
    PRIMARY_SPOUSE = "PRIMSPOUS"
    FAMILY_MEMBER = "FAMMEMB"
    CHILD = "CHILD"
    ADOPTED_CHILD = "CHLDADOPT"
    DAUGHTER = "DAU"
    SON = "SON"
    SPOUSE = "SPS"
    HUSBAND = "HUSB"
    WIFE = "WIFE"
    PARENT = "PRN"
    FATHER = "FTH"
    MOTHER = "MTH"
    SIBLING = "SIB"
    BROTHER = "BRO"
    SISTER = "SIS"
    GRANDPARENT = "GRPRN"
    GRANDFATHER = "GRFTH"
    GRANDMOTHER = "GRMTH"
    GRANDCHILD = "GRNDCHILD"
    AUNT = "AUNT"
    UNCLE = "UNCLE"
    NIECE = "NEICE"
    NEPHEW = "NEPHEW"
    COUSIN = "COUSN"
    DOMESTIC_PARTNER = "DOMPART"
    SIGNIFICANT_OTHER = "SIGOTHR"


class SearchStatusReasonCode(str, Enum):
    """SPDCI Search status reason codes.

    From social_api_v1.0.0.yaml SearchStatusReasonCode enum.
    Used in SearchResponseItem.status_reason_code when status='rjct'.
    """

    REFERENCE_ID_INVALID = "rjct.reference_id.invalid"
    REFERENCE_ID_DUPLICATE = "rjct.reference_id.duplicate"
    TIMESTAMP_INVALID = "rjct.timestamp.invalid"
    SEARCH_CRITERIA_INVALID = "rjct.search_criteria.invalid"
    FILTER_INVALID = "rjct.filter.invalid"
    SORT_INVALID = "rjct.sort.invalid"
    PAGINATION_INVALID = "rjct.pagination.invalid"
    TOO_MANY_RECORDS = "rjct.search.too_many_records_found"


class MsgHeaderStatusReasonCode(str, Enum):
    """SPDCI Message header status reason codes.

    From social_api_v1.0.0.yaml MsgHeaderStatusReasonCode enum.
    Used in DCICallbackHeader.status_reason_code.
    """

    VERSION_INVALID = "rjct.version.invalid"
    MESSAGE_ID_DUPLICATE = "rjct.message_id.duplicate"
    MESSAGE_TS_INVALID = "rjct.message_ts.invalid"
    ACTION_INVALID = "rjct.action.invalid"
    ACTION_NOT_SUPPORTED = "rjct.action.not_supported"
    TOTAL_COUNT_INVALID = "rjct.total_count.invalid"
    TOTAL_COUNT_LIMIT_EXCEEDED = "rjct.total_count.limit_exceeded"
    ERRORS_TOO_MANY = "rjct.errors.too_many"


class SubscribeStatusReasonCode(str, Enum):
    """SPDCI Subscribe status reason codes.

    From social_api_v1.0.0.yaml SubscribeStatusReasonCode enum.
    Used in SubscribeResponseItem.status_reason_code.
    """

    REFERENCE_ID_INVALID = "rjct.reference_id.invalid"
    REFERENCE_ID_DUPLICATE = "rjct.reference_id.duplicate"
    TIMESTAMP_INVALID = "rjct.timestamp.invalid"
    NOTIFY_TYPES_INVALID = "rjct.notify_types.invalid"
    NOTIFY_DETAILS_INVALID = "rjct.notify_details.invalid"
    PERSON_ID_INVALID = "rjct.person_id.invalid"
    ALREADY_SUBSCRIBED = "rjct.event.already_subscribed"


class UnsubscribeStatusReasonCode(str, Enum):
    """SPDCI Unsubscribe status reason codes.

    From social_api_v1.0.0.yaml UnsubscribeStatusReasonCode enum.
    Used in UnsubscribeResponseItem.status_reason_code.
    """

    REFERENCE_ID_INVALID = "rjct.reference_id.invalid"
    REFERENCE_ID_DUPLICATE = "rjct.reference_id.duplicate"
    TIMESTAMP_INVALID = "rjct.timestamp.invalid"
    SUBSCRIPTION_CODE_INVALID = "rjct.subscription_code.invalid"
    REQUESTER_INVALID = "rjct.requester.invalid"
    ALREADY_UNSUBSCRIBED = "rjct.event.already_unsubscribed"
