import json, tempfile, unittest
from pathlib import Path
from astra_intelligence.dataset.prepare import load_and_validate, split_by_group, DatasetError
from astra_intelligence.security.free_only import authorize_resource, PaidResourceBlocked
from astra_intelligence.evaluation.quality_gate import compare_reports

class SafetyTests(unittest.TestCase):
    def row(self, i):
        return {"prompt":f"Question {i}","response":f"Answer {i}","source":"user-reviewed","license":"CC-BY-4.0","verified":True,"task_type":"reasoning","group_id":f"group-{i}"}
    def test_verified_records_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.jsonl"
            good=self.row(1); bad=self.row(2); bad["verified"]=False
            p.write_text(json.dumps(good)+"\n"+json.dumps(bad)+"\n", encoding="utf-8")
            rows, report=load_and_validate(p)
            self.assertEqual(len(rows),1); self.assertEqual(report["rejected"],1)
    def test_group_split_no_leakage(self):
        rows=[self.row(i) for i in range(30)]
        splits, counts=split_by_group(rows)
        sets=[{r["group_id"] for r in splits[k]} for k in ("train","validation","test")]
        self.assertFalse(sets[0]&sets[1]); self.assertFalse(sets[0]&sets[2]); self.assertFalse(sets[1]&sets[2])
    def test_too_few_groups_rejected(self):
        with self.assertRaises(DatasetError): split_by_group([self.row(1),self.row(2)])
    def test_paid_resource_blocked(self):
        with self.assertRaises(PaidResourceBlocked): authorize_resource("gpu-vendor","paid")
    def test_free_resource_allowed(self):
        authorize_resource("local-cpu","local")
    def test_quality_gate_rejects_regression(self):
        base={k:.8 for k in ("overall","reasoning","hindi","coding","factuality","instruction_following")}
        cand=dict(base); cand["reasoning"]=.6; cand["overall"]=.9
        self.assertFalse(compare_reports(base,cand).accepted)
    def test_quality_gate_accepts_no_regression_and_gain(self):
        base={k:.7 for k in ("overall","reasoning","hindi","coding","factuality","instruction_following")}
        cand={k:.75 for k in base}
        self.assertTrue(compare_reports(base,cand).accepted)

if __name__ == "__main__": unittest.main()


# ---- Seetal: intelligence status tool (read-only) ----
def test_intelligence_status_reads_config():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.intelligence_status import status
    rep = status()
    assert rep["config_present"] is True
    assert rep["gates"]["policy_free_only"] is True
    assert rep["ready_to_promote"] is False


def test_intelligence_status_counts_examples(tmp_path):
    from tools.intelligence_status import status
    for split, n in (("train", 3), ("validation", 1), ("test", 1)):
        (tmp_path / f"{split}.jsonl").write_text("\n".join(['{"a":1}'] * n), encoding="utf-8")
    rep = status(tmp_path)
    assert rep["examples"] == {"train": 3, "validation": 1, "test": 1}
    assert rep["total_examples"] == 5
    assert rep["ready_to_train"] is False   # minimum 100 nahi mila
