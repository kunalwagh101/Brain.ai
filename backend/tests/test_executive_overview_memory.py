import uuid

from app.decision_memory_models import MemoryKind, MemoryState
from app.executive_overview import _aggregate_memories
from app.project_status import ProjectMemory, ProjectStatusSnapshot


def _snapshot(
    *,
    project_id: uuid.UUID,
    name: str,
    blocker: ProjectMemory | None = None,
    decision: ProjectMemory | None = None,
) -> ProjectStatusSnapshot:
    return ProjectStatusSnapshot(
        project_node_id=project_id,
        project_name=name,
        progress_percent=None,
        progress_basis="unconfigured",
        status="blocked" if blocker is not None else "unconfigured",
        progress_items=(),
        active_blockers=(blocker,) if blocker is not None else (),
        confirmed_decisions=(decision,) if decision is not None else (),
        candidate_memories=(),
        evidence=(),
    )


def test_confirmed_memory_is_deduplicated_and_keeps_all_visible_project_links() -> None:
    memory_id = uuid.uuid4()
    blocker = ProjectMemory(
        id=memory_id,
        kind=MemoryKind.BLOCKER,
        state=MemoryState.CONFIRMED,
        summary="Production credentials are missing",
        confidence=0.99,
        work_graph_node_id=uuid.uuid4(),
        canonical_event_id=uuid.uuid4(),
        search_document_id=uuid.uuid4(),
    )
    first_project = uuid.uuid4()
    second_project = uuid.uuid4()
    organization_id = uuid.uuid4()

    result = _aggregate_memories(
        organization_id,
        (
            _snapshot(project_id=first_project, name="Atlas", blocker=blocker),
            _snapshot(project_id=second_project, name="Beacon", blocker=blocker),
        ),
        attribute="active_blockers",
    )

    assert len(result) == 1
    assert result[0].id == memory_id
    assert result[0].state == MemoryState.CONFIRMED
    assert set(result[0].project_node_ids) == {first_project, second_project}
    assert set(result[0].project_names) == {"Atlas", "Beacon"}
    assert result[0].provenance.drilldown_path.endswith(f"/memory/{memory_id}")
