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

        println!("{:?}", call_graph);

        llvm_plugin::PreservedAnalyses::All
    }
}

pub struct ForkInfoWithDep {
    depth: usize,
}

impl ForkInfoWithDep {
    pub fn new(depth: usize) -> Self {
        ForkInfoWithDep { depth }
    }
}

impl llvm_plugin::LlvmModulePass for ForkInfoWithDep {
    fn run_pass(
        &self,
        module: &mut Module,
        manager: &llvm_plugin::ModuleAnalysisManager,
    ) -> llvm_plugin::PreservedAnalyses {
        let call_graph = manager.get_result::<CallGraphAnalysis>(module);
        let selected_functions = call_graph.find_callees_within_depth("main", self.depth);
        let function_manager = manager
            .get_function_analysis_manager_proxy(module)
            .get_manager();

        for func_value in module.get_functions() {
            let func_name = func_value.get_name().to_string_lossy().into_owned();
            if selected_functions.contains(&func_name) {
                let locations = function_manager.get_result::<ForkInstAnalysis>(&func_value);
                if locations.is_empty() {
                    continue;
                }
                println!("function: {}", func_name);
                for loc in locations {
                    println!("{}", loc);
                }
            }
        }

        llvm_plugin::PreservedAnalyses::All
    }
}
