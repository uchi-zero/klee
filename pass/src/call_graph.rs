use llvm_plugin::inkwell::values::{AnyValueEnum, FunctionValue, InstructionOpcode};
use llvm_plugin::inkwell::{values::AnyValue, values::BasicValueEnum};
use petgraph::graph::{DiGraph, NodeIndex};
use std::collections::HashMap;

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

    fn add_edge(&mut self, src: &String, dst: &String) {
        let src_idx = self.get_node_index(src);
        let dst_idx = self.get_node_index(dst);
        self.graph.add_edge(src_idx, dst_idx, ());
    }

    pub fn add_callees_from_function(&mut self, func: &FunctionValue) {
        let caller_name: String = func.get_name().to_string_lossy().into_owned();
        for bb in func.get_basic_block_iter() {
            for inst in bb.get_instructions() {
                let op = inst.get_opcode();
                if op != InstructionOpcode::Call && op != InstructionOpcode::Invoke {
                    continue;
                }
                let operand = match inst.get_operand(inst.get_num_operands() - 1) {
                    Some(o) => o,
                    None => continue,
                };
                let basic_val: BasicValueEnum = match operand.left() {
                    Some(v) => v,
                    None => continue,
                };

                if let AnyValueEnum::FunctionValue(callee) = basic_val.as_any_value_enum() {
                    let callee_name = callee.get_name().to_string_lossy().into_owned();
                    self.add_edge(&caller_name, &callee_name);
                }
            }
        }
    }
}
