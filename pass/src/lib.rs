mod analysis;
mod call_graph;
mod src_loc;
mod transformation;

use analysis::{CallGraphAnalysis, ForkInstAnalysis};
use transformation::{CallGraphPrinter, ForkInfoPrinter};

use crate::transformation::ForkInfoWithDep;

// Plugin registration
#[llvm_plugin::plugin(name = "klee_analysis", version = "0.1.0")]
fn plugin_registrar(builder: &mut llvm_plugin::PassBuilder) {
    builder.add_function_analysis_registration_callback(|manager| {
        manager.register_pass(ForkInstAnalysis);
    });

    builder.add_module_analysis_registration_callback(|manager| {
        manager.register_pass(CallGraphAnalysis);
    });

    builder.add_function_pipeline_parsing_callback(|name, manager| {
        if name == "fork-inst-printer" {
            manager.add_pass(ForkInfoPrinter);
            llvm_plugin::PipelineParsing::Parsed
        } else {
            llvm_plugin::PipelineParsing::NotParsed
        }
    });

    builder.add_module_pipeline_parsing_callback(|name, manager| {
        if let Some(depth_str) = name.strip_prefix("print-fork-info-") {
            if let Ok(depth) = depth_str.parse::<usize>() {
                manager.add_pass(ForkInfoWithDep::new(depth));
                return llvm_plugin::PipelineParsing::Parsed;
            }
        }
        if name == "call-graph-printer" {
            manager.add_pass(CallGraphPrinter);
            llvm_plugin::PipelineParsing::Parsed
        } else {
            llvm_plugin::PipelineParsing::NotParsed
        }
    });
}
