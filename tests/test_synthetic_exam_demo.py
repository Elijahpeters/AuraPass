from tools.synthetic_exam_demo import run_demo


def test_synthetic_exam_demo_runs_grant_and_denial_workflow(capsys):
    scenarios = run_demo()
    output = capsys.readouterr().out

    assert [item["decision"]["decision"] for item in scenarios] == [
        "GRANTED",
        "DENIED",
        "DENIED",
        "DENIED",
        "DENIED",
    ]
    assert scenarios[0]["decision"]["seat"] == 1
    assert scenarios[0]["decision"]["hardware_commands"] == [
        "V,DEMO-001,EEG501",
        "O,1",
    ]
    assert scenarios[1]["decision"]["reason"] == "Already scanned. Seat 1."
    assert scenarios[2]["decision"]["reason"] == "Student is not registered for today's course."
    assert scenarios[3]["decision"]["reason"] == "Hall capacity is full."
    assert scenarios[4]["decision"]["reason"] == "No synthetic match was supplied."
    assert "no biometric analysis is performed" in output
    assert "commands are printed and never transmitted" in output
