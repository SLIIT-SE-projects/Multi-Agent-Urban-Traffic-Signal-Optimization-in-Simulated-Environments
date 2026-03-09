import { useMemo } from 'react';

export const useNodeLoadMapper = (currentMetrics: any) => {
    return useMemo(() => {
        if (!currentMetrics?.intersections || !currentMetrics?.lanes) return { data: [], totalLoad: 0 };

        const intersections = currentMetrics.intersections;
        const lanes = currentMetrics.lanes;
        let globalTotalLoad = 0;

        const nodeLoadData = Object.keys(intersections).map((nodeId) => {
            let loadScore = 0;

            // Find all lanes feeding into this node and sum their queue lengths.
            // SUMO edge/lane IDs often follow the pattern: FROM_TO_index or similar, 
            // but realistically we can just check if the lane ID contains the nodeId as a destination.
            // A more exact check depends on the exact SUMO network convention, 
            // but a generic `laneId.includes(nodeId)` or checking if the lane feeds the node works as an approximation.
            Object.entries<any>(lanes).forEach(([laneId, laneData]) => {
                // For true accuracy, we'd need the network graph adjacency. 
                // Assuming SUMO standard naming `incomingEdge_to_nodeId...` or we just filter lanes that have queue > 0 
                // and are connected to this TLS. Since `gnnTelemetry` might not strictly link lane to node easily,
                // we will map based on string inclusion or prefix if known.
                if (laneId.includes(nodeId)) {
                    loadScore += (laneData.queue_length || 0);
                }
            });

            globalTotalLoad += loadScore;

            return {
                id: nodeId,
                data: [
                    {
                        x: 'Load',
                        y: loadScore
                    }
                ]
            };
        });

        // Sort descending so the largest bars are either center or outer depending on Nivo radial config
        nodeLoadData.sort((a, b) => b.data[0].y - a.data[0].y);

        return { data: nodeLoadData, totalLoad: globalTotalLoad };
    }, [currentMetrics]);
};
