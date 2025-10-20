"""
Prints a graph based on ontology_entities.csv.
"""
import csv
import networkx as nx
import matplotlib.pyplot as plt
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '../../ontology_entities.csv')

def print_ontology_graph(csv_path=CSV_PATH):
    G = nx.DiGraph()
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            src = row['Entity']
            action = row['Action']
            tgt = row['TargetEntity']
            label = f"{action}"
            G.add_edge(src, tgt, label=label)
    pos = nx.spring_layout(G)
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=2000, font_size=10)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='red')
    plt.show()

if __name__ == "__main__":
    print_ontology_graph()