mod src_loc;

use llvm_plugin::inkwell::values::{FunctionValue, InstructionOpcode};
use llvm_plugin::{
    AnalysisKey, FunctionAnalysisManager, LlvmFunctionAnalysis, LlvmFunctionPass, PassBuilder,
    PipelineParsing, PreservedAnalyses,
};
use src_loc::SourceLocation;

// Analysis pass that collects branch instructions with locations
struct ForkInstAnalysis;

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
                if inst.get_opcode() == InstructionOpcode::Br {
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

// Printer pass that queries the analysis and prints results
struct BranchPrinterPass;

impl LlvmFunctionPass for BranchPrinterPass {
    fn run_pass(
        &self,
        function: &mut FunctionValue,
        manager: &FunctionAnalysisManager,
    ) -> PreservedAnalyses {
        let locations = manager.get_result::<ForkInstAnalysis>(function);
        let function_name = function.get_name().to_str().unwrap();

        println!(
            "Function '{}' has {} branch instruction(s):",
            function_name,
            locations.len()
        );

        for loc in locations.iter() {
            println!("{:?}", loc);
        }

        PreservedAnalyses::All
    }
}

// Plugin registration
#[llvm_plugin::plugin(name = "branch_counter", version = "0.1")]
fn plugin_registrar(builder: &mut PassBuilder) {
    builder.add_function_analysis_registration_callback(|manager| {
        manager.register_pass(ForkInstAnalysis);
    });

    builder.add_function_pipeline_parsing_callback(|name, pass_manager| {
        if name == "branch-printer" {
            pass_manager.add_pass(BranchPrinterPass);
            PipelineParsing::Parsed
        } else {
            PipelineParsing::NotParsed
        }
    });
}
