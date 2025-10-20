"""
Ontology entity representing an intent and possible actions for other entities.
"""
class Entity:
    def __init__(self, name, intent, actions=None):
        self.name = name
        self.intent = intent
        self.actions = actions if actions is not None else []

    def add_action(self, action, target_entity):
        self.actions.append({"action": action, "target": target_entity})

    def get_actions(self):
        return self.actions