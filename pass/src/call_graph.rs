use llvm_plugin::inkwell;

pub type CallGraph = petgraph::graph::DiGraph<String, ()>;

trait MyGraphExt {
    fn add_callees_from_function(&mut self, func: &inkwell::values::FunctionValue);
}

impl MyGraphExt for CallGraph {
    fn add_callees_from_function(&mut self, func: &inkwell::values::FunctionValue) {
        todo!("implement");
    }
}
