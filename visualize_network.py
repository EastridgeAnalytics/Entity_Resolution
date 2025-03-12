# streamlit run visualize_network.py
import streamlit as st
import pandas as pd
import sqlalchemy
from neo4j import GraphDatabase
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle

# ============================================
# PARAMETERS (Modify these as needed)
# ============================================

# --- Neo4j Defaults (Default Data Source) ---
DB_NAME = "neo4j"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j12345"
# This Cypher query should return three columns: n, r, and m.
DEFAULT_CYPHER_QUERY = """
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100
"""
DEFAULT_DISPLAY_PROPERTY = "full_name"  # property to use for node display text
DEFAULT_NODE_LABEL = "Observation"      # fallback label if none is available

# --- SQL Defaults ---
SQL_CONN_STR = "sqlite:///example.db"
SQL_NODES_QUERY = "SELECT * FROM nodes_view LIMIT 100"
SQL_RELATIONSHIPS_QUERY = "SELECT * FROM relationships_view LIMIT 200"

# --- Schema Mapping for SQL (all properties are retained) ---
DEFAULT_NODE_ID_COL = "Node_ID"
DEFAULT_NODE_LABEL_COL = "Label"   # if missing, will default to DEFAULT_NODE_LABEL
DEFAULT_NODE_NAME_COL = "Name"

DEFAULT_REL_SOURCE_COL = "Source_ID"
DEFAULT_REL_TARGET_COL = "Target_ID"
DEFAULT_REL_TYPE_COL = "Relationship_Type"

# ============================================
# STREAMLIT APP CONFIGURATION & TITLE
# ============================================
st.set_page_config(page_title="Network Graph with All Properties", layout="wide")
st.title("Network Graph with All Node & Edge Properties")

# ============================================
# SIDEBAR: DATA SOURCE SELECTION & SETTINGS
# ============================================
data_source = st.sidebar.selectbox("Select Data Source", ["Neo4j", "Relational DB"], index=0)

# -------------------------------------------
# Neo4j Settings (Default Data Source)
# -------------------------------------------
if data_source == "Neo4j":
    st.sidebar.header("Neo4j Settings")
    db_name = st.sidebar.text_input("Database Name", value=DB_NAME)
    uri = st.sidebar.text_input("Neo4j URI", value=NEO4J_URI)
    user = st.sidebar.text_input("Neo4j Username", value=NEO4J_USER)
    password = st.sidebar.text_input("Neo4J Password", value=NEO4J_PASSWORD, type="password")
    cypher_query = st.sidebar.text_area("Cypher Query", value=DEFAULT_CYPHER_QUERY)
    display_property = st.sidebar.text_input("Display Property", value=DEFAULT_DISPLAY_PROPERTY)
    
# -------------------------------------------
# SQL Settings
# -------------------------------------------
elif data_source == "Relational DB":
    st.sidebar.header("Relational DB Settings")
    conn_str = st.sidebar.text_input("SQL Connection String", value=SQL_CONN_STR)
    nodes_query = st.sidebar.text_area("SQL Query for Nodes", value=SQL_NODES_QUERY)
    relationships_query = st.sidebar.text_area("SQL Query for Relationships", value=SQL_RELATIONSHIPS_QUERY)
    
    st.sidebar.markdown("### Schema Mapping")
    node_id_col = st.sidebar.text_input("Node ID Column", value=DEFAULT_NODE_ID_COL)
    node_label_col = st.sidebar.text_input("Node Label Column", value=DEFAULT_NODE_LABEL_COL)
    node_name_col = st.sidebar.text_input("Node Display Property Column", value=DEFAULT_NODE_NAME_COL)
    rel_source_col = st.sidebar.text_input("Relationship Source Column", value=DEFAULT_REL_SOURCE_COL)
    rel_target_col = st.sidebar.text_input("Relationship Target Column", value=DEFAULT_REL_TARGET_COL)
    rel_type_col = st.sidebar.text_input("Relationship Type Column", value=DEFAULT_REL_TYPE_COL)

# ============================================
# FUNCTIONS TO LOAD & TRANSFORM DATA
# ============================================

# If you want caching, uncomment the decorator below.
# @st.cache_data
def load_graph_data_neo4j(uri, user, password, db_name, query, display_property):
    """
    Connect to Neo4j, run a single query returning columns n, r, and m,
    and extract all properties from nodes (n, m) and relationship (r).
    
    We store:
      - Node properties: all from node.keys() plus 'id', 'labels' and a fallback label if needed.
      - Relationship properties: all from relationship.keys(), plus 'id', 'type', 'start', 'end'.
    """
    driver = GraphDatabase.driver(uri, auth=(user, password))
    nodes_dict = {}  # keyed by node ID (string)
    edges_list = []  # list of edge dicts

    with driver.session(database=db_name) as session:
        results = session.run(query)
        for record in results:
            n_obj = record["n"]
            r_obj = record["r"]
            m_obj = record["m"]

            # -- Process node n --
            n_id = str(n_obj.id)
            # If we haven't seen this node yet, gather its properties
            if n_id not in nodes_dict:
                # Extract all node properties
                n_data = {key: n_obj[key] for key in n_obj.keys()}
                # Additional meta info
                n_data["id"] = n_id
                # Store all labels (which is a frozenset in the official driver)
                labels = list(n_obj.labels)
                n_data["labels"] = labels
                # For display, choose a label or fallback
                display_label = ":".join(labels) if labels else DEFAULT_NODE_LABEL
                # The "label" field is the type of node we'll style by
                n_data["label"] = display_label
                # The "name" field is what st_link_analysis typically shows as node text
                n_data["name"] = n_data.get(display_property, display_label)
                nodes_dict[n_id] = n_data

            # -- Process node m --
            m_id = str(m_obj.id)
            if m_id not in nodes_dict:
                m_data = {key: m_obj[key] for key in m_obj.keys()}
                m_data["id"] = m_id
                labels = list(m_obj.labels)
                m_data["labels"] = labels
                display_label = ":".join(labels) if labels else DEFAULT_NODE_LABEL
                m_data["label"] = display_label
                m_data["name"] = m_data.get(display_property, display_label)
                nodes_dict[m_id] = m_data

            # -- Process relationship r --
            # Note: In official Neo4j driver, a Relationship object has:
            #   r_obj.id, r_obj.type, r_obj.start_node, r_obj.end_node, and r_obj.keys() for properties
            rel_data = {key: r_obj[key] for key in r_obj.keys()}  # all relationship properties
            # Add meta fields
            rel_data["id"] = str(r_obj.id)
            rel_data["source"] = str(r_obj.start_node.id)
            rel_data["target"] = str(r_obj.end_node.id)
            # We'll store 'label' in edges to define the relationship type in the graph
            rel_data["label"] = r_obj.type
            edges_list.append(rel_data)

    driver.close()

    # Build the final cytoscape-style elements
    elements = {
        "nodes": [{"data": data} for data in nodes_dict.values()],
        "edges": [{"data": edge} for edge in edges_list]
    }
    return elements

# If you want caching, uncomment the decorator below.
# @st.cache_data
def load_graph_data_sql(conn_str, nodes_query, relationships_query,
                        node_id_col, node_label_col, node_name_col,
                        rel_source_col, rel_target_col, rel_type_col):
    """
    Load nodes and relationships from SQL, retaining all columns as properties.
    """
    engine = sqlalchemy.create_engine(conn_str)
    nodes_df = pd.read_sql_query(nodes_query, engine)
    relationships_df = pd.read_sql_query(relationships_query, engine)
    
    elements = {"nodes": [], "edges": []}
    
    # Process nodes – include all properties.
    nodes_seen = set()
    for _, row in nodes_df.iterrows():
        node_data = row.to_dict()
        node_id = str(node_data.get(node_id_col))
        if node_id in nodes_seen:
            continue
        nodes_seen.add(node_id)
        node_data["id"] = node_id
        
        # Node label fallback
        node_label = node_data.get(node_label_col, "") or DEFAULT_NODE_LABEL
        node_data["label"] = node_label
        
        # Node display name fallback
        node_data["name"] = node_data.get(node_name_col, node_label)
        
        elements["nodes"].append({"data": node_data})
    
    # Process relationships – include all properties.
    for idx, row in relationships_df.iterrows():
        edge_data = row.to_dict()
        edge_data["id"] = f"edge_{idx}"
        edge_data["source"] = str(edge_data.get(rel_source_col))
        edge_data["target"] = str(edge_data.get(rel_target_col))
        edge_data["label"] = edge_data.get(rel_type_col, "RELATED")
        elements["edges"].append({"data": edge_data})
    
    return elements

def create_dynamic_styles(elements):
    """
    Create dynamic NodeStyle and EdgeStyle lists based on unique node labels and relationship types.
    """
    node_labels = set()
    rel_types = set()
    for node in elements["nodes"]:
        node_labels.add(node["data"].get("label", DEFAULT_NODE_LABEL))
    for edge in elements["edges"]:
        rel_types.add(edge["data"].get("label", "RELATED"))
    
    # Create node styles – each label gets a default color and icon.
    node_styles = []
    default_colors = ["#2A629A", "#FF7F3E", "#C0C0C0", "#008000", "#800080"]
    for i, label in enumerate(sorted(node_labels)):
        color = default_colors[i % len(default_colors)]
        node_styles.append(NodeStyle(label, color, "name", "circle"))
    
    # Create edge styles for each relationship type.
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
            st.success("Graph data loaded successfully from Neo4j!")
        except Exception as e:
            st.error(f"Error loading data from Neo4j: {e}")

elif data_source == "Relational DB":
    if st.sidebar.button("Load Data from Relational DB"):
        try:
            elements = load_graph_data_sql(conn_str, nodes_query, relationships_query,
                                           node_id_col, node_label_col, node_name_col,
                                           rel_source_col, rel_target_col, rel_type_col)
            st.success("Graph data loaded successfully from SQL!")
        except Exception as e:
            st.error(f"Error loading data from SQL: {e}")

# ============================================
# DISPLAY THE NETWORK GRAPH
# ============================================
if elements:
    node_styles, edge_styles = create_dynamic_styles(elements)
    st.header("Network Graph")
    st_link_analysis(
        elements,
        layout="cose",          # or try "circle", "grid", etc.
        node_styles=node_styles,
        edge_styles=edge_styles              # turn on zoom/pan
    )
else:
    st.info("Press the appropriate button in the sidebar to load data and display the graph.")
