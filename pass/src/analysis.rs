use crate::call_graph::CallGraph;
use crate::src_loc::SourceLocation;
use llvm_plugin::inkwell::module::Module;
use llvm_plugin::inkwell::values::{FunctionValue, InstructionOpcode};
use llvm_plugin::{
    AnalysisKey, FunctionAnalysisManager, LlvmFunctionAnalysis, LlvmModuleAnalysis,
    ModuleAnalysisManager,
};

pub struct ForkInstAnalysis;

impl LlvmFunctionAnalysis for ForkInstAnalysis {
    type Result = Vec<SourceLocation>;

    fn run_analysis(
        &self,
        function: &FunctionValue,
        _manager: &FunctionAnalysisManager,
    ) -> Self::Result {
        let mut locations = Vec::new();

        for bb in function.get_basic_blocks() {
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
