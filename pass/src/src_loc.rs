use llvm_plugin::inkwell::llvm_sys::debuginfo::{
    LLVMDIFileGetDirectory, LLVMDIFileGetFilename, LLVMDILocationGetColumn, LLVMDILocationGetLine,
    LLVMDILocationGetScope, LLVMDIScopeGetFile, LLVMInstructionGetDebugLoc,
};
use llvm_plugin::inkwell::values::{AsValueRef, InstructionValue};
use std::path::PathBuf;

/// Store branch info with location
#[derive(Debug)]
pub struct SourceLocation {
    filepath: PathBuf,
    line: u32,
    column: u32,
}

fn non_null<T>(ptr: *mut T) -> Option<*mut T> {
    if ptr.is_null() { None } else { Some(ptr) }
}

impl std::fmt::Display for SourceLocation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}:{}:{}",
            self.filepath.display(),
            self.line,
            self.column
        )
    }
}

impl SourceLocation {
    /// Extract branch information from an LLVM instruction
    pub fn from_instruction(inst: &InstructionValue) -> Option<Self> {
        unsafe {
            let debug_loc = non_null(LLVMInstructionGetDebugLoc(inst.as_value_ref()))?;
            let scope = non_null(LLVMDILocationGetScope(debug_loc))?;
            let file = non_null(LLVMDIScopeGetFile(scope))?;

            let mut filename_len: u32 = 0;
            let mut directory_len: u32 = 0;
            let filename_ptr = LLVMDIFileGetFilename(file, &mut filename_len);
            let directory_ptr = LLVMDIFileGetDirectory(file, &mut directory_len);

            let filename_str = if !filename_ptr.is_null() && filename_len > 0 {
                std::slice::from_raw_parts(filename_ptr as *const u8, filename_len as usize)
            } else {
                &[]
            };

            let directory_str = if !directory_ptr.is_null() && directory_len > 0 {
                std::slice::from_raw_parts(directory_ptr as *const u8, directory_len as usize)
            } else {
                &[]
            };
            if filename_str.is_empty() && directory_str.is_empty() {
                return None;
            }
            let path = if !directory_str.is_empty() {
                let dir = String::from_utf8_lossy(directory_str);
                let file = String::from_utf8_lossy(filename_str);
                PathBuf::from(dir.as_ref()).join(file.as_ref())
            } else {
                PathBuf::from(String::from_utf8_lossy(filename_str).as_ref())
            };

            return Some(SourceLocation {
                filepath: path,
                line: LLVMDILocationGetLine(debug_loc),
                column: LLVMDILocationGetColumn(debug_loc),
            });
        }
    }
}
