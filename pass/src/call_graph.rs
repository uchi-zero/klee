use inkwell::values::{AnyValueEnum, FunctionValue, InstructionOpcode};
use llvm_plugin::inkwell::{self, values::AnyValue};

pub type CallGraph = petgraph::graph::DiGraph<String, ()>;

pub trait LLVMExt {
    fn add_callees_from_function(&mut self, func: &FunctionValue);
}

impl LLVMExt for CallGraph {
    fn add_callees_from_function(&mut self, func: &FunctionValue) {
        let caller_name: String = func.get_name().to_string_lossy().into_owned();
        for bb in func.get_basic_block_iter() {
            for inst in bb.get_instructions() {
                if inst.get_opcode() == InstructionOpcode::Call {
                    let called_value = inst
                        .get_operand(inst.get_num_operands() - 1)
                        .unwrap()
                        .left() // An operand is Either<BasicValueEnum, BasicBlock>
                        .unwrap();

                    if let AnyValueEnum::FunctionValue(callee) = called_value.as_any_value_enum() {
                        let callee_name = callee.get_name().to_string_lossy().into_owned();

                        println!(
                            "Found direct call from '{}' to '{}'",
                            caller_name, callee_name
                        );
                    }
                }
            }
        }
    }
}
