from dataclasses import dataclass
from typing import Any


@dataclass
class LeafDomain:
    model: str
    domain: list


@dataclass
class AND:
    nodes: list[Any]


@dataclass
class OR:
    nodes: list[Any]


@dataclass
class NOT:
    node: Any


@dataclass
class ExistsThrough:
    through_model: str
    parent_field: str
    link_field: str
    child_model: str
    child_plan: Any
    default_domain: list | None = None


@dataclass
class CountThrough:
    through_model: str
    parent_field: str
    link_field: str
    child_model: str
    child_plan: Any
    op: str
    rhs: Any
    default_domain: list | None = None


@dataclass
class FieldAggregateThrough:
    """Aggregate a numeric field over members matching a filter and compare against rhs.

    Supports: sum, avg, min, max

    Examples:
        members.sum(m, m.income) >= 10000
        members.avg(m, m.age) > 25
        members.min(m, m.score) >= 0.5
        members.max(m, m.score) <= 1.0
    """

    through_model: str
    parent_field: str
    link_field: str
    child_model: str
    child_plan: Any
    agg_type: str  # 'sum', 'avg', 'min', 'max'
    agg_field: str  # The field to aggregate, e.g., 'income'
    op: str
    rhs: Any
    default_domain: list | None = None


@dataclass
class MetricCompare:
    """Represents a comparison against a metric value evaluated for the root subject.

    Example: metric('education.attendance_pct', me, '2024-09') >= 85
    """

    metric: str
    subject_var: str | None
    period_key: str | None
    params: dict | None
    op: str
    rhs: Any


@dataclass
class CoverageRequire:
    """Gate a plan by requiring minimum coverage for an inner MetricCompare.

    Only supported when the inner node is a MetricCompare; otherwise executor
    will raise NotImplementedError.
    """

    node: Any
    min_coverage: float


@dataclass
class AggMetricCompare:
    """Aggregate metric over a through relation and compare against rhs.

    Supports agg in { 'avg', 'coverage' } for Phase 2.
    """

    through_model: str
    parent_field: str
    link_field: str
    child_model: str
    metric: str
    period_key: str | None
    agg: str  # 'avg' | 'coverage'
    op: str
    rhs: Any
    default_domain: list | None = None


@dataclass
class ArithmeticCompare:
    """Compare an arithmetic expression over aggregates against a value.

    `dependency_ratio >= 1.5` expands to
    `(child_count + elderly_count) / max(1, working_age_count) >= 1.5`, which
    no Odoo domain can express: the value depends on counting related records
    per parent and then doing arithmetic on the results.

    Before this node existed such an expression fell through the translator's
    field resolution to the literal field `id`, producing `('id', '>=', 1.5)`
    and quietly matching every record.

    `expr` is the parsed left-hand side. The executor collects its aggregate
    leaves, resolves each to a {parent_id: value} map with one grouped read
    apiece, then evaluates the arithmetic per candidate. That keeps the cost
    at a few queries rather than one per record, but it is still a scan of the
    candidate set: no SQL fast path applies.
    """

    model: str
    expr: Any
    op: str
    rhs: Any
    cfg: dict | None = None


def flatten_and(nodes: list[Any]) -> list[Any]:
    out = []
    for n in nodes:
        if isinstance(n, AND):
            out.extend(flatten_and(n.nodes))
        else:
            out.append(n)
    return out
