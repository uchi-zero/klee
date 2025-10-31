use llvm_plugin::inkwell::values::{FunctionValue, InstructionOpcode};
use llvm_plugin::{AnalysisKey, FunctionAnalysisManager, LlvmFunctionAnalysis, PassBuilder};

#[llvm_plugin::plugin(name = "br_counter", version = "0.1")]
fn plugin_registrar(builder: &mut PassBuilder) {
    builder.add_function_analysis_registration_callback(|manager| {
        manager.register_pass(BranchCounterAnalysis);
    });
}

struct BranchCounterAnalysis;

impl LlvmFunctionAnalysis for BranchCounterAnalysis {
    type Result = usize;

    fn run_analysis(
        &self,
        function: &FunctionValue,
        _manager: &FunctionAnalysisManager,
    ) -> Self::Result {
        let mut count = 0;

        for basic_block in function.get_basic_blocks() {
            for instruction in basic_block.get_instructions() {
                if instruction.get_opcode() == InstructionOpcode::Br {
                    count += 1;
                }
            }
        }

        count
    }

    fn id() -> AnalysisKey {
        static ID: u8 = 0;
        &ID
    }
}
