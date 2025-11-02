mod analysis;
mod call_graph;
mod src_loc;

use analysis::ForkInstAnalysis;
use llvm_plugin::inkwell::values::FunctionValue;
use llvm_plugin::{
    FunctionAnalysisManager, LlvmFunctionPass, PassBuilder, PipelineParsing, PreservedAnalyses,
};

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
            "Function '{}' has {} fork instruction(s):",
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
