import pandas as pd

def extract_findings(document: dict) -> pd.DataFrame:
    rows = []

    review_id = str(document["_id"])
    created_at = document.get("created_at")

    recommendations = document.get("recommendations", {})

    for artifact_name, artifact in recommendations.items():
        agent_id = artifact.get("agent_id")

        for sec in artifact.get("sections", []):
            rows.append({
                "review_id": review_id,              # ✅ FIXED
                "created_at": str(created_at),        # ✅ SAFE
                "artifact": artifact_name,
                "agent": agent_id,
                "uuid": sec.get("uuid"),
                "section": sec.get("section_title"),
                "sentence": sec.get("sentence"),
                "page": sec.get("page_number"),
                "category": sec.get("category"),
                "rule": sec.get("rule_citation"),
                "recommendation": sec.get("recommendations"),
                "accept": sec.get("accept"),
                "accept_with_changes": sec.get("accept_with_changes"),
                "reject": sec.get("reject"),
            })

    return pd.DataFrame(rows)
