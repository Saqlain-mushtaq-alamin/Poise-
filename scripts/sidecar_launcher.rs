use std::env;
use std::os::windows::io::AsRawHandle;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[cfg(windows)]
fn assign_to_job_object(child_handle: std::os::windows::io::RawHandle) {
    use std::ptr::null_mut;
    type HANDLE = *mut std::ffi::c_void;
    type BOOL = i32;
    type DWORD = u32;

    #[repr(C)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        per_process_user_time_limit: i64,
        per_job_user_time_limit: i64,
        limit_flags: DWORD,
        minimum_working_set_size: usize,
        maximum_working_set_size: usize,
        active_process_limit: DWORD,
        affinity: usize,
        priority_class: DWORD,
        scheduling_class: DWORD,
    }

    #[repr(C)]
    struct IO_COUNTERS {
        read_operation_count: u64,
        write_operation_count: u64,
        other_operation_count: u64,
        read_transfer_count: u64,
        write_transfer_count: u64,
        other_transfer_count: u64,
    }

    #[repr(C)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        basic_limit_information: JOBOBJECT_BASIC_LIMIT_INFORMATION,
        io_info: IO_COUNTERS,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory_limit: usize,
        peak_job_memory_limit: usize,
    }

    extern "system" {
        fn CreateJobObjectW(lpJobAttributes: *mut std::ffi::c_void, lpName: *const u16) -> HANDLE;
        fn SetInformationJobObject(
            hJob: HANDLE,
            JobObjectInformationClass: i32,
            lpJobObjectInformation: *mut std::ffi::c_void,
            cbJobObjectInformationLength: DWORD,
        ) -> BOOL;
        fn AssignProcessToJobObject(hJob: HANDLE, hProcess: HANDLE) -> BOOL;
    }

    unsafe {
        let job = CreateJobObjectW(null_mut(), null_mut());
        if !job.is_null() {
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.basic_limit_information.limit_flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            SetInformationJobObject(
                job,
                9, // JobObjectExtendedLimitInformation
                &mut info as *mut _ as *mut std::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as DWORD,
            );
            AssignProcessToJobObject(job, child_handle as HANDLE);
            let _ = job;
        }
    }
}

fn find_python_and_backend() -> (PathBuf, PathBuf) {
    let current_exe = env::current_exe().unwrap_or_default();
    let exe_dir = current_exe.parent().unwrap_or(Path::new("."));

    let candidates = vec![
        (exe_dir.join("../../backend/.venv/Scripts/python.exe"), exe_dir.join("../../backend")),
        (exe_dir.join("../backend/.venv/Scripts/python.exe"), exe_dir.join("../backend")),
        (PathBuf::from("backend/.venv/Scripts/python.exe"), PathBuf::from("backend")),
        (PathBuf::from(".venv/Scripts/python.exe"), PathBuf::from(".")),
        (PathBuf::from(r"D:\canvas\Poise-\backend\.venv\Scripts\python.exe"), PathBuf::from(r"D:\canvas\Poise-\backend")),
    ];

    for (py, backend) in candidates {
        if py.exists() && backend.exists() {
            let py_canonical = py.canonicalize().unwrap_or(py);
            let backend_canonical = backend.canonicalize().unwrap_or(backend);
            return (py_canonical, backend_canonical);
        }
    }

    (PathBuf::from("python"), PathBuf::from("backend"))
}

fn main() {
    let (python_path, backend_dir) = find_python_and_backend();

    let mut cmd = Command::new(&python_path);
    cmd.arg("-u")
       .arg("-m")
       .arg("app.main")
       .current_dir(&backend_dir)
       .env("PYTHONUNBUFFERED", "1")
       .stdin(Stdio::inherit())
       .stdout(Stdio::inherit())
       .stderr(Stdio::inherit());

    let args: Vec<String> = env::args().skip(1).collect();
    if !args.is_empty() {
        cmd.args(&args);
    }

    match cmd.spawn() {
        Ok(mut child) => {
            #[cfg(windows)]
            assign_to_job_object(child.as_raw_handle());

            let status = child.wait().expect("failed to wait on python child process");
            std::process::exit(status.code().unwrap_or(0));
        }
        Err(err) => {
            eprintln!("Failed to spawn python backend (using {:?} in {:?}): {}", python_path, backend_dir, err);
            std::process::exit(1);
        }
    }
}
