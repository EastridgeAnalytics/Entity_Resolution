
This notebook demonstrates how to use Neo4j to identify and resolve duplicates caused by near-similarities in your database. The notebook covers the following steps:

1. **Pre-requisites**: 
    - Install necessary Python packages: `faker` and `neo4j`.
    - Ensure Neo4j database is set up with APOC and Graph Data Science (GDS) libraries enabled.

2. **Create Mock Data**:
    - Generates random candidate data using Faker.
    - Intentionally seeds near-duplicates to test entity resolution.

3. **Create "Fraud Family" Clusters**:
    - Programmatically creates two small demo clusters in Neo4j:
      1. A "fraud family" of 5 nodes with partial property overlaps.
      2. 6 variations of one person with minor differences.

4. **Normalize the Data**:
    - Applies normalization (stripping punctuation, lowercasing, etc.).
    - Writes back normalized fields (normalizedPhone, normalizedEmail, etc.).

5. **Run Entity Recognition**:
    - Creates indexes on normalized fields.
    - Sets up blocking keys.
    - Performs fuzzy matching (Jaro-Winkler, Levenshtein, etc.) on normalized fields.
    - Aggregates multiple SIMILAR relationships into AGGREGATED_SIMILAR.
    - Projects the subgraph into GDS for clustering (Leiden).
    - Optionally merges or links duplicates.

6. **Resolution**:
    - Creates MasterEntity nodes and links each Candidate to its corresponding MasterEntity node using the 'entityId' property.
    - Sets canonical values for each MasterEntity node based on the most common values in the cluster.

## How to Run

1. **Install Dependencies**:
    ```sh
    pip3 install faker neo4j
    # or
    conda install faker conda-forge::neo4j-python-driver
    ```

2. **Set Up Neo4j**:
    - Create a new database and update the URI, USER, PASSWORD, and DB_NAME in the notebook.
    - Ensure APOC and GDS libraries are enabled.

3. **Run the Notebook**:
    - Execute each cell in the notebook sequentially to perform entity resolution.

## Notes

- The notebook uses deterministic seeding for Faker to ensure reproducibility.
- The normalization functions handle common variations in phone numbers, emails, and addresses.
- The entity resolution pipeline uses a combination of blocking, fuzzy matching, and clustering to identify duplicates.
- The final resolution step creates MasterEntity nodes with canonical values based on the most common properties in each cluster.