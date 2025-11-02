use crate::call_graph::CallGraph;
use crate::src_loc::SourceLocation;

use llvm_plugin::inkwell::module::Module;
use llvm_plugin::inkwell::values::{FunctionValue, InstructionOpcode};
use llvm_plugin::{AnalysisKey, FunctionAnalysisManager, ModuleAnalysisManager};

pub struct ForkInstAnalysis;

impl llvm_plugin::LlvmFunctionAnalysis for ForkInstAnalysis {
    type Result = Vec<SourceLocation>;

    fn run_analysis(&self, func: &FunctionValue<'_>, _: &FunctionAnalysisManager) -> Self::Result {
        let mut locations = Vec::new();

        for bb in func.get_basic_block_iter() {
            for inst in bb.get_instructions() {
                if (inst.get_opcode() == InstructionOpcode::Br
                    || inst.get_opcode() == InstructionOpcode::Switch)
                    && inst.get_num_operands() > 1
                {
                    if let Some(info) = SourceLocation::from_instruction(&inst) {
                        locations.push(info);
                    }
                }
            }
        }

        locations
    }

    fn id() -> AnalysisKey {
        static ID: u8 = 0;
        &ID
    }
}

pub struct CallGraphAnalysis;

impl llvm_plugin::LlvmModuleAnalysis for CallGraphAnalysis {
    type Result = CallGraph;

    fn run_analysis(&self, module: &Module<'_>, _: &ModuleAnalysisManager) -> Self::Result {
        let mut graph = CallGraph::new();

        for function in module.get_functions() {
            graph.add_callees_from_function(&function);
        }

        graph
    }

    fn id() -> AnalysisKey {
        static ID: u8 = 1;
        &ID
    }
}
