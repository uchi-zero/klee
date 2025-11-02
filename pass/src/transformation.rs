use crate::analysis::{CallGraphAnalysis, ForkInstAnalysis};
use llvm_plugin::inkwell::{module::Module, values::FunctionValue};

pub struct ForkInfoPrinter;

impl llvm_plugin::LlvmFunctionPass for ForkInfoPrinter {
    fn run_pass(
        &self,
        function: &mut FunctionValue,
        manager: &llvm_plugin::FunctionAnalysisManager,
    ) -> llvm_plugin::PreservedAnalyses {
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

        llvm_plugin::PreservedAnalyses::All
    }
}

pub struct CallGraphPrinter;

impl llvm_plugin::LlvmModulePass for CallGraphPrinter {
    fn run_pass(
        &self,
        module: &mut Module,
        manager: &llvm_plugin::ModuleAnalysisManager,
    ) -> llvm_plugin::PreservedAnalyses {
        let call_graph = manager.get_result::<CallGraphAnalysis>(module);
        let module_name = module.get_name().to_str().unwrap();

        println!(
            "Module '{}' has a call graph with {} nodes and {} edges:",
            module_name,
            call_graph.node_count(),
            call_graph.edge_count()
        );

        for node in call_graph.node_indices() {
            let node_name = call_graph[node].clone();
            println!("Node '{}'", node_name);
        }

        for edge in call_graph.edge_indices() {
            let (source, target) = call_graph.edge_endpoints(edge).unwrap();
            let source_name = call_graph[source].clone();
            let target_name = call_graph[target].clone();
            println!("Edge from '{}' to '{}'", source_name, target_name);
        }

        llvm_plugin::PreservedAnalyses::All
    }
}
