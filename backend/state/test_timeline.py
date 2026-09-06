import pytest
from backend.state.timeline import TimelineEmitter

def test_timeline_emits_all_contract_events():
    emitter = TimelineEmitter()
    
    received_events = []
    def listener(event):
        received_events.append(event)
        
    emitter.subscribe(listener)
    
    # Simulate a full happy path + interruption event flow
    emitter.emit_task_created("t1", "what is this", "2026-09-06T10:00:00Z")
    emitter.emit_task_active("t1")
    emitter.emit_task_tool_running("t1", "get_sales")
    emitter.emit_task_obsolete("t1", "t2")
    
    emitter.emit_task_created("t2", "actually what is Q2", "2026-09-06T10:01:00Z")
    emitter.emit_task_active("t2", "t1")
    emitter.emit_task_generating("t2")
    emitter.emit_task_speaking("t2", "speech-uuid-1")
    emitter.emit_task_completed("t2")
    
    # Assert counts
    assert len(emitter.history) == 9
    assert len(received_events) == 9
    
    # Assert schemas exactly match CONTRACTS.md
    assert received_events[0]["event_name"] == "task.created"
    assert received_events[0]["task_id"] == "t1"
    assert "timestamp" in received_events[0]
    assert received_events[0]["payload"]["request_text"] == "what is this"
    
    assert received_events[1]["event_name"] == "task.active"
    assert received_events[1]["payload"]["previous_task_id"] is None
    
    assert received_events[3]["event_name"] == "task.obsolete"
    assert received_events[3]["payload"]["superseded_by_task_id"] == "t2"
    
    assert received_events[5]["event_name"] == "task.active"
    assert received_events[5]["payload"]["previous_task_id"] == "t1"
    
    assert received_events[7]["event_name"] == "task.speaking"
    assert received_events[7]["payload"]["speech_id"] == "speech-uuid-1"

def test_error_and_cancelled():
    emitter = TimelineEmitter()
    
    emitter.emit_task_cancelled("t3", "user hung up")
    emitter.emit_task_failed("t4", "LLM timeout")
    
    assert emitter.history[0]["event_name"] == "task.cancelled"
    assert emitter.history[0]["payload"]["reason"] == "user hung up"
    
    assert emitter.history[1]["event_name"] == "task.failed"
    assert emitter.history[1]["payload"]["error"] == "LLM timeout"
