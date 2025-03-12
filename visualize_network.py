
import pandas as pd
import sqlalchemy
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle

# ============================================
# Load environment variables
# ============================================
load_dotenv()

DEFAULT_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DEFAULT_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j12345")
DEFAULT_DB_NAME = os.getenv("NEO4J_DB_NAME", "neo4j")

# ============================================
# OTHER DEFAULTS
# ============================================
DEFAULT_CYPHER_QUERY = """
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100
"""
DEFAULT_DISPLAY_PROPERTY = "full_name"
DEFAULT_NODE_LABEL = "Observation"

# SQL Defaults
SQL_CONN_STR = "sqlite:///example.db"
SQL_NODES_QUERY = "SELECT * FROM nodes_view LIMIT 100"
SQL_RELATIONSHIPS_QUERY = "SELECT * FROM relationships_view LIMIT 200"

# Schema mapping for SQL
DEFAULT_NODE_ID_COL = "Node_ID"
DEFAULT_NODE_LABEL_COL = "Label"
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
data_source = st.sidebar.selectbox(
    "Select Data Source", 
    ["Neo4j", "Relational DB"], 
    index=0,
    key="data_source_select"
)

# -------------------------------------------
# Neo4j Settings (Default Data Source)
# -------------------------------------------
if data_source == "Neo4j":
    st.sidebar.header("Neo4j Settings")
    db_name = st.sidebar.text_input(
        "Database Name",
        value=DEFAULT_DB_NAME,
        key="neo4j_db_name"
    )
    uri = st.sidebar.text_input(
        "Neo4j URI",
        value=DEFAULT_NEO4J_URI,
        key="neo4j_uri"
    )
    user = st.sidebar.text_input(
        "Neo4j Username",
        value=DEFAULT_NEO4J_USER,
        key="neo4j_user"
    )
    password = st.sidebar.text_input(
        "Neo4j Password",
        value=DEFAULT_NEO4J_PASSWORD,
        type="password",
        key="neo4j_password"
    )
    cypher_query = st.sidebar.text_area(
        "Cypher Query",
        value=DEFAULT_CYPHER_QUERY,
        key="cypher_query"
    )
    display_property = st.sidebar.text_input(
        "Display Property",
        value=DEFAULT_DISPLAY_PROPERTY,
        key="display_property"
    )

# -------------------------------------------
# SQL Settings
# -------------------------------------------
elif data_source == "Relational DB":
    st.sidebar.header("Relational DB Settings")
    conn_str = st.sidebar.text_input(
        "SQL Connection String",
        value=SQL_CONN_STR,
        key="sql_conn_str"
    )
    nodes_query = st.sidebar.text_area(
        "SQL Query for Nodes",
        value=SQL_NODES_QUERY,
        key="sql_nodes_query"
    )
    relationships_query = st.sidebar.text_area(
        "SQL Query for Relationships",
        value=SQL_RELATIONSHIPS_QUERY,
        key="sql_relationships_query"
    )
    
    st.sidebar.markdown("### Schema Mapping")
    node_id_col = st.sidebar.text_input(
        "Node ID Column",
        value=DEFAULT_NODE_ID_COL,
        key="node_id_col"
    )
    node_label_col = st.sidebar.text_input(
        "Node Label Column",
        value=DEFAULT_NODE_LABEL_COL,
        key="node_label_col"
    )
    node_name_col = st.sidebar.text_input(
        "Node Display Property Column",
        value=DEFAULT_NODE_NAME_COL,
        key="node_name_col"
    )
    rel_source_col = st.sidebar.text_input(
        "Relationship Source Column",
        value=DEFAULT_REL_SOURCE_COL,
        key="rel_source_col"
    )
    rel_target_col = st.sidebar.text_input(
        "Relationship Target Column",
        value=DEFAULT_REL_TARGET_COL,
        key="rel_target_col"
    )
    rel_type_col = st.sidebar.text_input(
        "Relationship Type Column",
        value=DEFAULT_REL_TYPE_COL,
        key="rel_type_col"
    )

# ============================================
# HELPER FOR JSON SERIALIZATION OF DATETIMES
# ============================================
def make_json_serializable(value):
    """Converts date/time objects (or lists/dicts of them) to ISO strings."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    elif isinstance(value, list):
        return [make_json_serializable(v) for v in value]
    elif isinstance(value, dict):
        return {k: make_json_serializable(v) for k, v in value.items()}
    else:
        return value

def to_json_compatible_properties(original_dict):
    """Recursively convert dictionary values to JSON-serializable forms."""
    converted = {}
    for k, v in original_dict.items():
        converted[k] = make_json_serializable(v)
    return converted

# ============================================
# FUNCTIONS TO LOAD & TRANSFORM DATA
# ============================================
def load_graph_data_neo4j(uri, user, password, db_name, query, display_property):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, password))
    nodes_dict = {}
    edges_list = []

    with driver.session(database=db_name) as session:
        results = session.run(query)
        for record in results:
            n_obj = record["n"]
            r_obj = record["r"]
            m_obj = record["m"]

            # Process node n
            n_id = str(n_obj.id)
            if n_id not in nodes_dict:
                n_data = {key: n_obj[key] for key in n_obj.keys()}
                n_data = to_json_compatible_properties(n_data)
                n_data["id"] = n_id
                labels = list(n_obj.labels)
                n_data["labels"] = labels
                display_label = ":".join(labels) if labels else DEFAULT_NODE_LABEL
                n_data["label"] = display_label
                n_data["name"] = n_data.get(display_property, display_label)
                nodes_dict[n_id] = n_data

            # Process node m
            m_id = str(m_obj.id)
            if m_id not in nodes_dict:
                m_data = {key: m_obj[key] for key in m_obj.keys()}
                m_data = to_json_compatible_properties(m_data)
                m_data["id"] = m_id
                labels = list(m_obj.labels)
                m_data["labels"] = labels
                display_label = ":".join(labels) if labels else DEFAULT_NODE_LABEL
                m_data["label"] = display_label
                m_data["name"] = m_data.get(display_property, display_label)
                nodes_dict[m_id] = m_data

            # Process relationship r
            rel_data = {key: r_obj[key] for key in r_obj.keys()}
            rel_data = to_json_compatible_properties(rel_data)
            rel_data["id"] = str(r_obj.id)
            rel_data["source"] = str(r_obj.start_node.id)
            rel_data["target"] = str(r_obj.end_node.id)
            rel_data["label"] = r_obj.type
            edges_list.append(rel_data)

    driver.close()
    return {
        "nodes": [{"data": d} for d in nodes_dict.values()],
        "edges": [{"data": e} for e in edges_list]
    }

def load_graph_data_sql(conn_str, nodes_query, relationships_query,
                        node_id_col, node_label_col, node_name_col,
                        rel_source_col, rel_target_col, rel_type_col):
    engine = sqlalchemy.create_engine(conn_str)
    nodes_df = pd.read_sql_query(nodes_query, engine)
    relationships_df = pd.read_sql_query(relationships_query, engine)
    
    elements = {"nodes": [], "edges": []}
    nodes_seen = set()

    # Nodes
    for _, row in nodes_df.iterrows():
        node_data = row.to_dict()
        node_id = str(node_data.get(node_id_col))
        if node_id in nodes_seen:
            continue
        nodes_seen.add(node_id)
        node_data = to_json_compatible_properties(node_data)
        node_data["id"] = node_id
        node_label = node_data.get(node_label_col, "") or DEFAULT_NODE_LABEL
        node_data["label"] = node_label
        node_data["name"] = node_data.get(node_name_col, node_label)
        elements["nodes"].append({"data": node_data})

    # Edges
    for idx, row in relationships_df.iterrows():
        edge_data = row.to_dict()
        edge_data = to_json_compatible_properties(edge_data)
        edge_data["id"] = f"edge_{idx}"
        edge_data["source"] = str(edge_data.get(rel_source_col))
        edge_data["target"] = str(edge_data.get(rel_target_col))
        edge_data["label"] = edge_data.get(rel_type_col, "RELATED")
        elements["edges"].append({"data": edge_data})
    return elements

def create_dynamic_styles(elements):
    node_labels = set()
    rel_types = set()
    for node in elements["nodes"]:
        node_labels.add(node["data"].get("label", DEFAULT_NODE_LABEL))
    for edge in elements["edges"]:
        rel_types.add(edge["data"].get("label", "RELATED"))

    node_styles = []
    default_colors = ["#2A629A", "#FF7F3E", "#C0C0C0", "#008000", "#800080"]
    for i, label in enumerate(sorted(node_labels)):
        color = default_colors[i % len(default_colors)]
        node_styles.append(NodeStyle(label, color, "name", "circle"))

    edge_styles = []
    for rel in sorted(rel_types):
        edge_styles.append(EdgeStyle(rel, caption=None, directed=True))

    return node_styles, edge_styles

# ============================================
# LOAD DATA AND DISPLAY GRAPH
# ============================================
elements = None

if data_source == "Neo4j":
    if st.sidebar.button("Load Data from Neo4j", key="neo4j_load_button"):
        try:
            elements = load_graph_data_neo4j(uri, user, password, db_name, cypher_query, display_property)
            st.success("Graph data loaded successfully from Neo4j!")
        except Exception as e:
            st.error(f"Error loading data from Neo4j: {e}")

elif data_source == "Relational DB":
    if st.sidebar.button("Load Data from Relational DB", key="sql_load_button"):
        try:
            elements = load_graph_data_sql(
                conn_str,
                nodes_query,
                relationships_query,
                node_id_col,
                node_label_col,
                node_name_col,
                rel_source_col,
                rel_target_col,
                rel_type_col
            )
            st.success("Graph data loaded successfully from SQL!")
        except Exception as e:
            st.error(f"Error loading data from SQL: {e}")

if elements:
    node_styles, edge_styles = create_dynamic_styles(elements)
    st.header("Network Graph")
    st_link_analysis(
        elements,
        layout="cose",
        node_styles=node_styles,
        edge_styles=edge_styles,
        zoom=True
    )
else:
    st.info("Press the appropriate button in the sidebar to load data and display the graph.")