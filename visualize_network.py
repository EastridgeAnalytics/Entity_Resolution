# streamlit run visualize_network.py

import streamlit as st
import pandas as pd
import sqlalchemy
from neo4j import GraphDatabase
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle

# ============================================
# PARAMETERS (Modify these as needed)
# ============================================

# ---------------------------
# Neo4j Parameters & Query
# ---------------------------
DB_NAME = "neo4j"
NEO4J_URI = "bolt://localhost:7689"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j12345"
# Single Cypher query that returns nodes (n and m) and relationships (r)
DEFAULT_CYPHER_QUERY = """
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100
"""
# The property to display on each node (e.g., "name")
DEFAULT_DISPLAY_PROPERTY = "name"
# Fallback node label if none exist
DEFAULT_NODE_LABEL = "Observation"

# ---------------------------
# SQL Parameters & Queries
# ---------------------------
SQL_CONN_STR = "sqlite:///example.db"
SQL_NODES_QUERY = "SELECT * FROM nodes_view LIMIT 100"
SQL_RELATIONSHIPS_QUERY = "SELECT * FROM relationships_view LIMIT 200"

# Flexible schema mapping for SQL (adjust if your column names differ)
DEFAULT_NODE_ID_COL = "Node_ID"
DEFAULT_NODE_LABEL_COL = "Label"    # If missing, defaults to DEFAULT_NODE_LABEL
DEFAULT_NODE_NAME_COL = "Name"

DEFAULT_REL_SOURCE_COL = "Source_ID"
DEFAULT_REL_TARGET_COL = "Target_ID"
DEFAULT_REL_TYPE_COL = "Relationship_Type"

# ============================================
# STREAMLIT APP CONFIGURATION & TITLE
# ============================================
st.set_page_config(page_title="Flexible Network Graph", layout="wide")
st.title("Flexible Network Graph with st_link_analysis")

# ============================================
# SIDEBAR: DATA SOURCE SELECTION & SETTINGS
# ============================================
# Data source selector: default is Neo4j.
data_source = st.sidebar.selectbox("Select Data Source", ["Neo4j", "SQL"], index=0)

if data_source == "Neo4j":
    st.sidebar.header("Neo4j Settings")
    db_name = st.sidebar.text_input("Database Name", value=DB_NAME)
    uri = st.sidebar.text_input("Neo4j URI", value=NEO4J_URI)
    user = st.sidebar.text_input("Neo4j Username", value=NEO4J_USER)
    password = st.sidebar.text_input("Neo4j Password", value=NEO4J_PASSWORD, type="password")
    cypher_query = st.sidebar.text_area("Cypher Query", value=DEFAULT_CYPHER_QUERY)
    display_property = st.sidebar.text_input("Display Property", value=DEFAULT_DISPLAY_PROPERTY)
else:
    st.sidebar.header("SQL Settings")
    conn_str = st.sidebar.text_input("SQL Connection String", value=SQL_CONN_STR)
    nodes_query = st.sidebar.text_area("SQL Query for Nodes", value=SQL_NODES_QUERY)
    relationships_query = st.sidebar.text_area("SQL Query for Relationships", value=SQL_RELATIONSHIPS_QUERY)
    st.sidebar.markdown("### Schema Mapping (SQL)")
    node_id_col = st.sidebar.text_input("Node ID Column", value=DEFAULT_NODE_ID_COL)
    node_label_col = st.sidebar.text_input("Node Label Column", value=DEFAULT_NODE_LABEL_COL)
    node_name_col = st.sidebar.text_input("Node Name Column", value=DEFAULT_NODE_NAME_COL)
    rel_source_col = st.sidebar.text_input("Relationship Source Column", value=DEFAULT_REL_SOURCE_COL)
    rel_target_col = st.sidebar.text_input("Relationship Target Column", value=DEFAULT_REL_TARGET_COL)
    rel_type_col = st.sidebar.text_input("Relationship Type Column", value=DEFAULT_REL_TYPE_COL)

# ============================================
# FUNCTIONS TO LOAD AND TRANSFORM DATA
# ============================================

def load_graph_data_neo4j(uri, user, password, db_name, query, display_property):
    """Load graph data from Neo4j using a single Cypher query."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    nodes = {}  # keyed by node id (as string)
    edges = []  # list of relationship dicts

    with driver.session(database=db_name) as session:
        result = session.run(query)
        for record in result:
            # Expecting record keys "n", "r", and "m"
            n = record.get("n")
            r = record.get("r")
            m = record.get("m")
            # Process node n
            n_id = str(n.id)
            if n_id not in nodes:
                n_labels = list(n.labels) if n.labels else [DEFAULT_NODE_LABEL]
                n_label = n_labels[0] if n_labels else DEFAULT_NODE_LABEL
                n_display = n.get(display_property, n_label)
                nodes[n_id] = {"id": n_id, "label": n_label, "name": n_display}
            # Process node m
            m_id = str(m.id)
            if m_id not in nodes:
                m_labels = list(m.labels) if m.labels else [DEFAULT_NODE_LABEL]
                m_label = m_labels[0] if m_labels else DEFAULT_NODE_LABEL
                m_display = m.get(display_property, m_label)
                nodes[m_id] = {"id": m_id, "label": m_label, "name": m_display}
            # Process relationship r
            edge = {
                "id": f"edge_{r.id}",
                "source": n_id,
                "target": m_id,
                "label": r.type  # automatically extracts relationship type
            }
            edges.append(edge)
    
    driver.close()
    # Assemble into the st_link_analysis elements format.
    elements = {
        "nodes": [{"data": data} for data in nodes.values()],
        "edges": [{"data": edge} for edge in edges]
    }
    return elements

def load_graph_data_sql(conn_str, nodes_query, relationships_query,
                        node_id_col, node_label_col, node_name_col,
                        rel_source_col, rel_target_col, rel_type_col):
    """Load graph data from a relational database using SQL queries for nodes and relationships."""
    engine = sqlalchemy.create_engine(conn_str)
    nodes_df = pd.read_sql_query(nodes_query, engine)
    relationships_df = pd.read_sql_query(relationships_query, engine)
    
    elements = {"nodes": [], "edges": []}
    
    # Process nodes: use flexible schema mapping.
    for _, row in nodes_df.iterrows():
        node_id = row[node_id_col] if node_id_col in nodes_df.columns else row.iloc[0]
        label = row[node_label_col] if node_label_col in nodes_df.columns else DEFAULT_NODE_LABEL
        name = row[node_name_col] if node_name_col in nodes_df.columns and pd.notnull(row[node_name_col]) else str(label)
        node_data = {"id": node_id, "label": label, "name": name}
        elements["nodes"].append({"data": node_data})
    
    # Process relationships.
    for idx, row in relationships_df.iterrows():
        source = row[rel_source_col] if rel_source_col in relationships_df.columns else None
        target = row[rel_target_col] if rel_target_col in relationships_df.columns else None
        rel_type = row[rel_type_col] if rel_type_col in relationships_df.columns else "RELATED"
        edge_data = {"id": f"edge_{idx}", "source": source, "target": target, "label": rel_type}
        # Add extra relationship properties, if any.
        for col in relationships_df.columns:
            if col not in [rel_source_col, rel_target_col, rel_type_col]:
                edge_data[col] = row[col]
        elements["edges"].append({"data": edge_data})
    
    return elements

def create_dynamic_styles(elements):
    """Dynamically create NodeStyle and EdgeStyle based on unique labels."""
    node_labels = set()
    rel_types = set()
    for node in elements["nodes"]:
        node_labels.add(node["data"].get("label", DEFAULT_NODE_LABEL))
    for edge in elements["edges"]:
        rel_types.add(edge["data"].get("label", "RELATED"))
    
    # Define a list of default colors for nodes.
    default_colors = ["#2A629A", "#FF7F3E", "#C0C0C0", "#008000", "#800080"]
    node_styles = []
    for i, label in enumerate(sorted(node_labels)):
        color = default_colors[i % len(default_colors)]
        node_styles.append(NodeStyle(label, color, "name", "circle"))
    
    edge_styles = []
    for rel in sorted(rel_types):
        edge_styles.append(EdgeStyle(rel, caption=None, directed=True))
    
    return node_styles, edge_styles

# ============================================
# LOAD DATA BASED ON THE SELECTED DATA SOURCE
# ============================================
elements = None
if data_source == "Neo4j":
    if st.sidebar.button("Load Data from Neo4j"):
        try:
            elements = load_graph_data_neo4j(uri, user, password, db_name, cypher_query, display_property)
            st.success("Graph data loaded from Neo4j successfully!")
        except Exception as e:
            st.error(f"Error loading data from Neo4j: {e}")
elif data_source == "SQL":
    if st.sidebar.button("Load Data from SQL"):
        try:
            elements = load_graph_data_sql(conn_str, nodes_query, relationships_query,
                                           node_id_col, node_label_col, node_name_col,
                                           rel_source_col, rel_target_col, rel_type_col)
            st.success("Graph data loaded from SQL successfully!")
        except Exception as e:
            st.error(f"Error loading data from SQL: {e}")

# ============================================
# DISPLAY THE NETWORK GRAPH
# ============================================
if elements:
    node_styles, edge_styles = create_dynamic_styles(elements)
    st.header("Network Graph")
    st_link_analysis(elements, layout="cose", node_styles=node_styles, edge_styles=edge_styles)
else:
    st.info("Press the appropriate 'Load Data' button in the sidebar to display the graph.")
