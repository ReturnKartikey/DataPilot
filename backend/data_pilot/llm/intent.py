"""LLM intent parsing. Outputs a constrained plan; never executes model-generated code."""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from typing import Any

def _fallback(question: str, columns: list[str]) -> dict[str,Any]:
    q=question.lower()
    kind="descriptive"
    if any(w in q for w in ["why","reason","cause","decline","contribut"]): kind="diagnostic"
    if any(w in q for w in ["predict","forecast","estimate","churn"]): kind="predictive"
    if any(w in q for w in ["recommend","optimize","optimise","allocate","what should","budget"]): kind="prescriptive"
    target=next((c for c in columns if c.lower() in q),None)
    group=next((c for c in columns if c.lower() in q and c!=target),None)
    return {"analytics_type":kind,"question":question,"target":target,"column":target,"group_by":group,
            "problem_type":"unknown","objective":"maximize","limit":10,"provider":"deterministic_fallback",
            "notice":"LLM unavailable; intent was inferred using conservative keyword matching. Review the plan."}

def _call_openai(key, model, question, columns):
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    default_base = "https://openrouter.ai/api/v1" if provider == "openrouter" else "https://api.openai.com/v1"
    base=(os.getenv("LLM_BASE_URL") or default_base).rstrip("/")
    schema={"type":"object","properties":{
      "analytics_type":{"type":"string","enum":["descriptive","diagnostic","predictive","prescriptive"]},
      "target":{"type":["string","null"]},"column":{"type":["string","null"]},
      "group_by":{"type":["string","null"]},"problem_type":{"type":"string","enum":["unknown","classification","regression"]},
      "objective":{"type":"string","enum":["maximize","minimize"]},"limit":{"type":"integer","minimum":1,"maximum":50}},
      "required":["analytics_type","target","column","group_by","problem_type","objective","limit"],"additionalProperties":False}
    prompt={"question":question,"available_columns":columns,"instruction":"The user supplied a natural-language QUESTION about the dataset, not necessarily a machine-learning objective, target feature, or problem type. Answering descriptive questions is the default. Set target=null and problem_type=unknown unless the question explicitly asks to predict/forecast/classify a named outcome. Map columns only when the question requires a particular field for the requested analysis. Never infer that the last or only potential target column was explicitly supplied by the user. Never invent columns. Return a plan only."}
    response_format = (
        {"type": "json_schema", "json_schema": {"name": "analytics_intent", "strict": True, "schema": schema}}
        if os.getenv("LLM_RESPONSE_FORMAT", "json_object").lower() == "json_schema"
        else {"type": "json_object"}
    )
    # OpenRouter (and several OpenAI-compatible providers) require the literal
    # word "JSON" in at least one message whenever response_format=json_object
    # is requested. Keep this instruction for json_schema too for portability.
    system_message = (
        "You are Data Pilot's analytical question router. The user is asking a question about the uploaded dataset, not declaring a target feature or ML problem by default. "
        "Treat descriptive questions as descriptive and leave target/problem_type null/unknown unless prediction, forecasting, or classification is explicitly requested. "
        "Return the plan as valid JSON matching the requested response format. "
        "Do not calculate results, generate code, or invent column names."
    )
    prompt["output_format"] = (
        "Return one valid JSON object only. Include every required schema key. "
        "Use null for unknown column mappings."
    )
    body={"model":model,"temperature":0,"response_format":response_format,
          "messages":[{"role":"system","content":system_message},
                      {"role":"user","content":json.dumps(prompt, ensure_ascii=False)}]}
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}
    if os.getenv("LLM_PROVIDER", "").lower() == "openrouter":
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173")
        headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "Data Pilot")
    req=urllib.request.Request(base+"/chat/completions",data=json.dumps(body).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=int(os.getenv("LLM_INTENT_TIMEOUT_SECONDS", "12"))) as r: raw=json.loads(r.read())
    except urllib.error.HTTPError as exc:
        # Keep provider diagnostics actionable without ever exposing credentials.
        detail = exc.read(1200).decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM provider HTTP {exc.code}: {detail[:500]}") from exc
    return json.loads(raw["choices"][0]["message"]["content"])

def _call_gemini(key, model, question, columns):
    prompt=("Interpret the user's natural-language question about the dataset; it is not automatically a target-feature or ML-problem declaration. Descriptive questions are the default. Set target null and problem_type unknown unless prediction/forecasting/classification is explicitly requested. Return only JSON with keys analytics_type (descriptive|diagnostic|predictive|prescriptive), "
      "target, column, group_by (exact column names or null), problem_type (unknown|classification|regression), objective (maximize|minimize), limit (integer). "
      "Never invent columns or compute results.\nAvailable columns: "+json.dumps(columns)+"\nQuestion: "+question)
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","temperature":0}}
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=int(os.getenv("LLM_INTENT_TIMEOUT_SECONDS", "12"))) as r: raw=json.loads(r.read())
    return json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])

def understand_intent(question: str, columns: list[str]) -> dict[str,Any]:
    provider=os.getenv("LLM_PROVIDER","openrouter").lower()
    key = (
        os.getenv("GEMINI_API_KEY") if provider == "gemini"
        else (os.getenv("OPENROUTER_API_KEY") if provider == "openrouter"
              else (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")))
    )
    if not key: return _fallback(question,columns)
    model=os.getenv("LLM_MODEL", "gemini-2.0-flash" if provider=="gemini" else ("openai/gpt-4o-mini" if provider=="openrouter" else "gpt-4o-mini"))
    try:
        plan=_call_gemini(key,model,question,columns) if provider=="gemini" else _call_openai(key,model,question,columns)
        allowed={"descriptive","diagnostic","predictive","prescriptive"}
        if plan.get("analytics_type") not in allowed: raise ValueError("Invalid analytics type")
        for keyname in ("target","column","group_by"):
            value=plan.get(keyname)
            if value is not None and value not in columns: plan[keyname]=None
        plan.update({"question":question,"provider":provider})
        return plan
    except Exception as exc:
        result=_fallback(question,columns)
        result["notice"]=f"LLM request failed: {str(exc)[:260]}; conservative fallback used."
        return result
