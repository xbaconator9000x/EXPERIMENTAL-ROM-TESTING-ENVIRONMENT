"""Opt-in controller with no language model and preserved checkpoint identity.

Existing native skills keep control. Unsupported states park for review
instead of fabricating inputs, invoking Ollama, or consuming GPU resources.
"""
class NativeOnly:
    native_only=True
    def __init__(self,model_name="qwen3-vl:4b-instruct"):
        # Legacy label is retained only for checkpoint identity compatibility.
        self.model=model_name
        self.fallback_requests=0
    def decide(self,rgb,goal,history,blocked):
        self.fallback_requests+=1
        return {"scene":"native_state_unclassified",
                "objective":"Require a verified native action before continuing",
                "actions":[],"review":True}
