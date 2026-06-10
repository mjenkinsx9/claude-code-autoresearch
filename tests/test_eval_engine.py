import json

import agent_cli
import eval_engine

CRITERIA = [{"id": 1, "question": "Q1?"}, {"id": 2, "question": "Q2?"}]


def _stub_response(payload):
    def fake_run(prompt, **kwargs):
        return agent_cli.AgentResult(
            backend="stub", returncode=0, stdout=payload, stderr="", command="stub",
        )
    return fake_run


def test_garbage_list_of_strings_falls_back(monkeypatch):
    monkeypatch.setattr(eval_engine, "run_agent_prompt", _stub_response('["yes", "no"]'))
    result = eval_engine.evaluate_single_output("output", CRITERIA)
    assert result["total_yes"] == 0
    assert "error" in result


def test_nonlist_json_falls_back(monkeypatch):
    monkeypatch.setattr(eval_engine, "run_agent_prompt", _stub_response('{"passed": true}'))
    result = eval_engine.evaluate_single_output("output", CRITERIA)
    assert result["total_yes"] == 0
    assert "error" in result


def test_extra_entries_cannot_exceed_criteria_count(monkeypatch):
    payload = json.dumps([
        {"criterion": i, "question": "q", "passed": True, "evidence": "e"}
        for i in range(10)
    ])
    monkeypatch.setattr(eval_engine, "run_agent_prompt", _stub_response(payload))
    result = eval_engine.evaluate_single_output("output", CRITERIA)
    assert result["total_yes"] == len(CRITERIA)


def test_eval_prompt_delimits_untrusted_output():
    prompt = eval_engine.build_eval_prompt("SOME OUTPUT", CRITERIA)
    assert "<<<OUTPUT_START>>>" in prompt
    assert "<<<OUTPUT_END>>>" in prompt
    assert "not instructions" in prompt.lower()
    # The untrusted output sits between the delimiters
    start = prompt.index("<<<OUTPUT_START>>>")
    end = prompt.index("<<<OUTPUT_END>>>")
    assert "SOME OUTPUT" in prompt[start:end]
