import osmnx as ox
import networkx as nx
from shapely.geometry import Point

class LocalDiversionEngine:
    def __init__(self, lat, lon, dist=3000):
        """
        Initializes the road network graph around a specific central point.
        dist=3000 downloads a 3km radius graph (perfect for localized diversions).
        """
        print("🤖 Loading local Bangalore road graph from OpenStreetMap...")
        # network_type='drive' filters out walkways, bike paths, etc.
        self.G = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
        
        # Add travel times to edges based on speed limits
        self.G = ox.add_edge_speeds(self.G)
        self.G = ox.add_edge_travel_times(self.G)
        
        # Keep a clean backup copy of the original graph structure
        self.original_G = self.G.copy()
        print(f"✅ Graph loaded successfully with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.")

    def reset_graph(self):
        """Resets the graph back to normal state (clears all temporary roadblocks)."""
        self.G = self.original_G.copy()

    def calculate_incident_diversions(self, incident_lat, incident_lon):
        """
        Finds the blocked edge, severs it, identifies all approaching roads,
        and computes localized diversion routes around the incident point.
        """
        # 1. Find the nearest edge to the reported incident
        nearest_edge = ox.nearest_edges(self.G, incident_lon, incident_lat)
        u_node, v_node, key = nearest_edge
        
        print(f"\n🚨 Incident detected on road segment between Node {u_node} and Node {v_node}")
        
        # Capture the attributes of the blocked edge before removal
        edge_data = self.G.get_edge_data(u_node, v_node, key)
        road_name = edge_data.get('name', 'Unnamed Road')
        print(f"🚧 Closing segment: {road_name} ({int(edge_data.get('length', 0))} meters long)")

        # 2. SEVER THE WIRE: Remove the edge from the active routing graph
        if self.G.has_edge(u_node, v_node):
            self.G.remove_edge(u_node, v_node)
        
        # Handle two-way roads if applicable
        if self.G.has_edge(v_node, u_node):
            self.G.remove_edge(v_node, u_node)

        # 3. IDENTIFY DIVERSION SOURCES: Find all roads feeding into the blocked node (u_node)
        # In-edges represent vehicles currently driving toward the point of blockage
        approaching_edges = self.original_G.in_edges(u_node, data=True)
        
        diversion_manifest = []

        # 4. COMPUTE FLANKS FOR ALL APPROACHING TRAFFIC
        for source_node, _, data in approaching_edges:
            # Skip if the source node is the other side of the same road
            if source_node == v_node:
                continue
                
            incoming_road_name = data.get('name', 'Connecting Street')
            print(f"🛣️  Calculating local diversion for traffic coming from: {incoming_road_name}")
            
            try:
                # Run local Dijkstra pathfinding from the intersection before the block
                # to the recovery node right past the block
                diversion_path = nx.shortest_path(self.G, source=source_node, target=v_node, weight='travel_time')
                
                # Convert node paths back to coordinates for your Leaflet frontend
                coordinates = []
                for node in diversion_path:
                    node_data = self.G.nodes[node]
                    coordinates.append([node_data['y'], node_data['x']]) # [lat, lon]
                
                diversion_manifest.append({
                    "from_road": incoming_road_name,
                    "target_recovery_node": v_node,
                    "coordinates": coordinates,
                    "status": "Diversion Calculated Successfully"
                })
            except nx.NetworkXNoPath:
                print(f"⚠️ No alternative path found for traffic coming from {incoming_road_name}!")
                diversion_manifest.append({
                    "from_road": incoming_road_name,
                    "status": "FAILED - Complete Gridlock"
                })

        return diversion_manifest

# --- QUICK VERIFICATION TEST USING YOUR BANGALORE COORDINATES ---
if __name__ == "__main__":
    # Center the local graph around the Frazer Town / RT Nagar area from your map
    center_lat, center_lon = 13.0035, 77.5785
    engine = LocalDiversionEngine(center_lat, center_lon, dist=12000)
    
    # Simulate a sudden roadblock in the middle of an intersection
    incident_lat, incident_lon = 13.0074, 77.6185
    routes = engine.calculate_incident_diversions(incident_lat, incident_lon)
    
    print(f"\n📊 Total active diversions computed: {len(routes)}")