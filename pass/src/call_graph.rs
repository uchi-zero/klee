use llvm_plugin::inkwell::values::{CallSiteValue, FunctionValue};
use petgraph::graph::{DiGraph, NodeIndex};
use std::collections::{HashMap, HashSet, VecDeque};

#[derive(Debug, Default)]
pub struct CallGraph {
    pub graph: DiGraph<String, ()>,
    node_map: HashMap<String, NodeIndex>,
}

impl CallGraph {
    pub fn new() -> Self {
        Self::default()
    }

    fn get_node_index(&mut self, name: &str) -> NodeIndex {
        if let Some(&index) = self.node_map.get(name) {
            return index;
        }
        // Node not found, so add it
        let name_owned = name.to_string();
        let index = self.graph.add_node(name_owned.clone());
        self.node_map.insert(name_owned, index);
        index
    }

    fn valid_callee(&self, name: &str) -> bool {
        if name.starts_with("llvm") || name.starts_with("__") {
            return false;
        }
        true
    }

    fn add_edge(&mut self, src: &String, dst: &String) {
        let src_idx = self.get_node_index(src);
        let dst_idx = self.get_node_index(dst);
        if !self.graph.contains_edge(src_idx, dst_idx) {
            self.graph.add_edge(src_idx, dst_idx, ());
        }
    }

    pub fn add_callees_from_function(&mut self, func: &FunctionValue) {
        let caller_name: String = func.get_name().to_string_lossy().into_owned();
        for bb in func.get_basic_block_iter() {
            for inst in bb.get_instructions() {
                if let Ok(call_site) = CallSiteValue::try_from(inst) {
                    if let Some(callee) = call_site.get_called_fn_value() {
                        let callee_name = callee.get_name().to_string_lossy().into_owned();
                        if self.valid_callee(&callee_name) {
                            self.add_edge(&caller_name, &callee_name);
                        }
                    }
                }
            }
        }
    }

    pub fn find_callees_within_depth(&self, caller: &str, max_depth: usize) -> Vec<String> {
        let caller_idx = match self.node_map.get(caller) {
            Some(&index) => index,
            // If the starting function doesn't exist in the graph, return an empty vector.
            None => return vec![],
        };

        // A queue to hold nodes to visit: (node_index, current_depth).
        let mut queue = VecDeque::new();
        queue.push_back((caller_idx, 0));

        // A set to store the names of functions we've found to ensure uniqueness.
        let mut found_functions = HashSet::new();
        found_functions.insert(caller.to_string());

        // A set to track visited nodes to prevent getting stuck in recursive cycles.
        let mut visited_nodes = HashSet::new();
        visited_nodes.insert(caller_idx);

        // Perform the Breadth-First Search.
        while let Some((current_node_idx, current_depth)) = queue.pop_front() {
            // Stop exploring from this path if we've reached the depth limit.
            if current_depth >= max_depth {
                continue;
            }

            // Explore all functions called by the current function (its neighbors).
            for neighbor_index in self.graph.neighbors(current_node_idx) {
                // `visited_nodes.insert()` returns true if the node was not already present.
                if visited_nodes.insert(neighbor_index) {
                    // Get the function name from its index.
                    if let Some(callee_name) = self.graph.node_weight(neighbor_index) {
                        found_functions.insert(callee_name.clone());
                    }

                    // Add the neighbor to the queue to be explored later.
                    queue.push_back((neighbor_index, current_depth + 1));
                }
            }
        }

        // Convert the set of names into a vector and return it.
        found_functions.into_iter().collect()
    }
}
