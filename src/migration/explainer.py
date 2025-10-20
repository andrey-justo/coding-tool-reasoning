"""
Explains the analysis results: why, how, and unsafe changes.
"""
class Explainer:
    def __init__(self, analysis):
        self.analysis = analysis

    def explain(self):
        why = self.analysis.get("why", "")
        how = self.analysis.get("how", "")
        unsafe = self.analysis.get("unsafe", "")
        return why, how, unsafe