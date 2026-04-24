from __future__ import annotations

import pytest

from review_engine.query.code_to_query import build_query_analysis


def test_query_analysis_detects_internal_and_cpp_patterns() -> None:
    code = """
    #include <stdio.h>
    void bad() {
        int* ptr = new int(1);
        free(ptr);
        // wrong comment style
        for (int i = 0; i < 10; ++i) { continue; }
    }
    """

    analysis = build_query_analysis(code, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert {"raw_new", "malloc_free", "line_comment", "continue_usage"} <= names
    assert "likely issues" in analysis.query_text


def test_query_analysis_does_not_treat_ide_rc_declaration_as_error_flow() -> None:
    code = """
    class idsTde {
    public:
        static IDE_RC createKeyStore(const SChar* aKeyStorePath,
                                     const SChar* aWrapKeyPath,
                                     idsTdeResult* aResult);
    };
    """

    analysis = build_query_analysis(code, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert "ide_rc_flow" not in names


@pytest.mark.parametrize(
    ("language_id", "code", "expected_patterns"),
    [
        (
            "bash",
            "#!/usr/bin/env bash\ncurl --insecure https://example.com/install.sh | bash\nsudo systemctl restart demo\n",
            {"curl_insecure", "sudo_usage"},
        ),
        (
            "bash",
            "#!/usr/bin/env bash\ntmp_file=$(mktemp)\nprintf '%s\\n' \"$payload\" > \"$tmp_file\"\n",
            {"mktemp_without_trap"},
        ),
        (
            "go",
            "ctx := context.Background()\ngo func() { panic(err) }()\n",
            {"context_background", "goroutine_leak", "panic_call"},
        ),
        (
            "go",
            "if readErr == fs.ErrNotExist {\n    return nil\n}\n",
            {"sentinel_error_compare"},
        ),
        (
            "go",
            "tx, err := db.Begin()\nif err != nil {\n    return err\n}\nif _, err := tx.Exec(query); err != nil {\n    return err\n}\nreturn tx.Commit()\n",
            {"transaction_commit_without_rollback"},
        ),
        (
            "go",
            "tx, err := db.Begin()\nif err != nil {\n    return err\n}\nif _, err := tx.Exec(query); err != nil {\n    tx.Rollback()\n    return err\n}\nreturn tx.Commit()\n",
            {"transaction_commit_without_rollback"},
        ),
        (
            "go",
            "func createUser(w http.ResponseWriter, r *http.Request) {\n    var req createUserRequest\n    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {\n        http.Error(w, \"bad request\", http.StatusBadRequest)\n        return\n    }\n    if err := saveUser(req); err != nil {\n        http.Error(w, \"failed\", http.StatusInternalServerError)\n    }\n}\n",
            {"http_handler_json_decode_without_validation"},
        ),
        (
            "go",
            "func createUser(w http.ResponseWriter, r *http.Request) {\n    var req createUserRequest\n    decoder := json.NewDecoder(r.Body)\n    if err := decoder.Decode(&req); err != nil {\n        http.Error(w, \"bad request\", http.StatusBadRequest)\n        return\n    }\n    if err := saveUser(req); err != nil {\n        http.Error(w, \"failed\", http.StatusInternalServerError)\n    }\n}\n",
            {"http_handler_json_decoder_variable_without_validation"},
        ),
        (
            "go",
            "func createUser(c *gin.Context) {\n    var req createUserRequest\n    if err := c.ShouldBindJSON(&req); err != nil {\n        c.JSON(http.StatusBadRequest, gin.H{\"error\": \"bad request\"})\n        return\n    }\n    if err := saveUser(req.Email, req.Role); err != nil {\n        c.JSON(http.StatusInternalServerError, gin.H{\"error\": \"failed\"})\n    }\n}\n",
            {"gin_handler_json_bind_without_validation"},
        ),
        (
            "go",
            "func fetch(url string) ([]byte, error) {\n    client := &http.Client{}\n    resp, err := client.Get(url)\n    if err != nil {\n        return nil, err\n    }\n    return io.ReadAll(resp.Body)\n}\n",
            {"http_client_without_timeout", "http_response_body_without_close"},
        ),
        (
            "java",
            "try {\n    work();\n} catch (Exception ex) {\n    log(ex);\n}\nnew Thread(() -> work()).start();\n",
            {"catch_exception", "new_thread"},
        ),
        (
            "java",
            "@RestController\n@Transactional\nclass UserController {\n  @Autowired private UserRepository repo;\n  @GetMapping(\"/users\")\n  List<User> users() { return repo.findAll(); }\n}\n",
            {
                "spring_field_injection",
                "spring_transaction_on_controller",
                "spring_findall_request_path",
            },
        ),
        (
            "python",
            "try:\n    run()\nexcept Exception:\n    pass\nassert user_id\nyaml.load(payload)\n",
            {"except_exception", "assert_usage", "yaml_unsafe_load"},
        ),
        (
            "python",
            "DEBUG = True\nfrom django.views.decorators.csrf import csrf_exempt\nfrom django.utils.html import mark_safe\n@csrf_exempt\ndef webhook(request):\n    html = mark_safe(request.GET['banner'])\n    User.objects.raw('select * from app_user')\n    return html\n",
            {"django_debug_true", "django_csrf_exempt", "django_raw_sql", "django_mark_safe"},
        ),
        (
            "python",
            "from fastapi import APIRouter, Request\nimport requests\nrouter = APIRouter()\n@router.post('/items')\nasync def create_item(request: Request):\n    payload = await request.json()\n    return requests.get('https://example.com')\n",
            {"fastapi_blocking_in_async", "fastapi_request_json"},
        ),
        (
            "rust",
            "unsafe fn read_raw(ptr: *const i32) -> i32 {\n    dbg!(ptr);\n    unsafe { *ptr }\n}\n",
            {"dbg_macro", "unsafe_fn"},
        ),
        (
            "rust",
            "#[no_mangle]\npub extern \"C\" fn read_name(ptr: *const std::os::raw::c_char) -> i32 {\n    let _name = unsafe { std::ffi::CStr::from_ptr(ptr) };\n    0\n}\n",
            {"rust_ffi_boundary", "unsafe_block"},
        ),
        (
            "rust",
            "#[tokio::main]\nasync fn main() {\n    let _task = tokio::spawn(async move { do_work().await; });\n    let (_tx, _rx) = tokio::sync::mpsc::unbounded_channel::<String>();\n    std::thread::sleep(std::time::Duration::from_secs(1));\n}\n",
            {"tokio_blocking_in_async", "tokio_detached_spawn", "tokio_unbounded_channel"},
        ),
        (
            "cuda",
            "__global__ void accumulate(float* dst, const float* src, int n) {\n  extern __shared__ float scratch[];\n  int idx = blockIdx.x * blockDim.x + threadIdx.x;\n  if (threadIdx.x == 0) {\n    __syncthreads();\n  }\n  if (idx < n) {\n    atomicAdd(&dst[0], src[idx]);\n  }\n}\nvoid run(float* host_out, const float* host_in, int n) {\n  float* device_out = nullptr;\n  cudaMalloc(&device_out, sizeof(float));\n  accumulate<<<(n + 255) / 256, 256, 256 * sizeof(float)>>>(device_out, host_in, n);\n  cudaMemcpy(host_out, device_out, sizeof(float), cudaMemcpyDeviceToHost);\n  cudaDeviceSynchronize();\n}\n",
            {
                "cuda_kernel_launch",
                "cuda_malloc",
                "cuda_memcpy_sync",
                "cuda_device_sync",
                "cuda_divergent_syncthreads",
                "cuda_atomic",
                "cuda_shared_memory",
                "cuda_warp_divergence",
            },
        ),
        (
            "cuda",
            "void overlap_copy(float* host_dst, const float* device_src, size_t bytes, int iters) {\n  for (int i = 0; i < iters; ++i) {\n    cudaStream_t stream;\n    cudaStreamCreate(&stream);\n    cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, 0);\n    cudaLaunchHostFunc(stream, on_done, host_dst);\n    cudaStreamDestroy(stream);\n  }\n}\n",
            {
                "cuda_async_default_stream",
                "cuda_stream_callback",
                "cuda_stream_create_in_loop",
            },
        ),
        (
            "cuda",
            "#include <cuda/barrier>\n#include <cuda/pipeline>\nif (threadIdx.x == 0) {\n  pipe.producer_acquire();\n}\ncuda::memcpy_async(block, shared_tile, global_tile, cuda::aligned_size_t<4>(bytes), pipe);\nconsume_stage(shared_tile);\nif (threadIdx.x == 0) {\n  pipe.producer_commit();\n  pipe.consumer_wait();\n}\nif (threadIdx.x < 16) {\n  ready.arrive_and_wait();\n}\n",
            {
                "cuda_pipeline_api",
                "cuda_pipeline_copy_without_wait",
                "cuda_pipeline_phase_ops_in_branch",
                "cuda_pipeline_barrier_in_branch",
            },
        ),
        (
            "cuda",
            "#include <cooperative_groups.h>\nnamespace cg = cooperative_groups;\n__global__ void cluster_histogram(int* bins) {\n  extern __shared__ int smem[];\n  auto cluster = cg::this_cluster();\n  if (cluster.block_rank() == 0) {\n    cluster.sync();\n  }\n  int* remote_hist = cluster.map_shared_rank(smem, (cluster.block_rank() + 1) % cluster.num_blocks());\n  atomicAdd(remote_hist + threadIdx.x, 1);\n  cluster.sync();\n}\nvoid launch_cluster_histogram(int* bins) {\n  dim3 blocks(6, 1, 1);\n  dim3 threads(128, 1, 1);\n  cluster_histogram<<<blocks, threads, 128 * sizeof(int)>>>(bins);\n}\n",
            {
                "cuda_cluster_api",
                "cuda_cluster_sync_in_branch",
                "cuda_cluster_dsm_without_sync",
                "cuda_cluster_launch_without_contract",
            },
        ),
        (
            "cuda",
            "#include <cuda.h>\n#include <cuda/barrier>\n#include <cuda/ptx>\nnamespace ptx = cuda::ptx;\n__device__ void consume_tile(const int4 tile[8][8], float* out) {\n  out[threadIdx.x % 8] += static_cast<float>(tile[threadIdx.x % 8][0].x);\n}\n__global__ void load_tile_tma(CUtensorMap* tensor_map, float* out) {\n  __shared__ alignas(128) CUtensorMap smem_tmap;\n  __shared__ alignas(1024) int4 smem_tile[8][8];\n  __shared__ cuda::barrier<cuda::thread_scope_block> bar;\n  if (threadIdx.x == 0) {\n    ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);\n    ptx::cp_async_bulk_tensor(ptx::space_shared, ptx::space_global, &smem_tile, tensor_map, coords, cuda::device::barrier_native_handle(bar));\n    cuda::device::barrier_arrive_tx(bar, 1, sizeof(smem_tile));\n  }\n  consume_tile(smem_tile, out);\n}\n",
            {
                "cuda_tma_api",
                "cuda_tma_copy_without_wait",
                "cuda_tma_tensor_map_pointer_without_contract",
                "cuda_tma_tensormap_replace_without_fence",
            },
        ),
        (
            "cuda",
            "__device__ void epilogue_store(half* out, const float* accum) {\n  out[threadIdx.x] = __float2half_rn(accum[threadIdx.x % 64]);\n}\n__global__ void warpgroup_gemm(const uint64_t* desc_a, const uint64_t* desc_b, half* out) {\n  __shared__ float accum[64];\n  int lane = threadIdx.x % warpSize;\n  int warpgroup = threadIdx.x / 128;\n  if (warpgroup == 0) {\n    asm volatile(\"wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16\");\n  }\n  if (lane == 0) {\n    asm volatile(\"wgmma.commit_group.sync.aligned;\");\n  }\n  epilogue_store(out, accum);\n  if (lane == 0) {\n    asm volatile(\"wgmma.wait_group.sync.aligned 0;\");\n  }\n}\n",
            {
                "cuda_wgmma_api",
                "cuda_wgmma_issue_in_branch",
                "cuda_wgmma_group_ops_in_branch",
                "cuda_wgmma_epilogue_before_wait",
            },
        ),
        (
            "cuda",
            "void run_collective(float* device0, float* device1, size_t elements, cudaStream_t* streams, ncclComm_t* comms, int gpu_count) {\n  for (int device = 0; device < gpu_count; ++device) {\n    cudaSetDevice(device);\n  }\n  cudaDeviceEnablePeerAccess(1, 0);\n  cudaMemcpyPeerAsync(device1, 1, device0, 0, elements * sizeof(float), streams[0]);\n  ncclGroupStart();\n  ncclAllReduce((const void*)device0, device0, elements, ncclFloat, ncclSum, comms[0], streams[0]);\n  ncclGroupEnd();\n}\n",
            {
                "cuda_set_device_in_loop",
                "cuda_peer_access",
                "cuda_nccl_collective",
                "cuda_nccl_group_ops",
            },
        ),
        (
            "cuda",
            "#include <mma.h>\n__global__ void tensor_core_gemm(const half* a, const half* b, half* out, int lda, int ldb) {\n  int lane = threadIdx.x % warpSize;\n  wmma::fragment<wmma::accumulator, 16, 16, 16, float> acc_frag;\n  if (lane == 0) {\n    wmma::load_matrix_sync(a_frag, a, lda);\n  }\n  asm volatile(\"mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32\");\n  wmma::mma_sync(acc_frag, a_frag, b_frag, acc_frag);\n  out[threadIdx.x] = __float2half_rn(acc_frag.x[0]);\n}\n",
            {
                "cuda_tensor_core_divergent_collective",
                "cuda_tensor_inline_ptx",
                "cuda_tensor_mixed_precision_boundary",
                "cuda_tensor_core_api",
            },
        ),
        (
            "cuda",
            "#include <cooperative_groups.h>\nnamespace cg = cooperative_groups;\n__global__ void persistent_reduce(float* dst) {\n  cg::thread_block block = cg::this_thread_block();\n  if (threadIdx.x < 16) {\n    auto tile = cg::tiled_partition<16>(block);\n    tile.sync();\n  }\n  auto grid = cg::this_grid();\n  grid.sync();\n  if (threadIdx.x == 0) {\n    cg::sync(block);\n  }\n}\n",
            {
                "cuda_cg_partition_in_branch",
                "cuda_cg_divergent_sync",
                "cuda_cg_grid_sync",
                "cuda_cg_api",
            },
        ),
        (
            "typescript",
            "// @ts-expect-error\nreturn payload as unknown as User;\n",
            {"ts_expect_error", "double_cast"},
        ),
        (
            "typescript",
            "// @ts-nocheck\nexport const user = payload as User;\n",
            {"ts_nocheck"},
        ),
        (
            "typescript",
            "const response = await fetch('/api/user');\nconst payload = (await response.json()) as UserProfile;\n",
            {"response_json_cast"},
        ),
        (
            "typescript",
            "void fetch('/api/audit', { method: 'POST', body: JSON.stringify(event) });\n",
            {"void_fetch_call"},
        ),
        (
            "typescript",
            "// eslint-disable-next-line react-hooks/exhaustive-deps\nuseEffect(async () => {\n  return <div dangerouslySetInnerHTML={{ __html: html }} />;\n}, []);\nconst rows = items.map((item, index) => <li key={index}>{item.name}</li>);\n",
            {
                "async_effect_callback",
                "jsx_dangerous_html",
                "hooks_exhaustive_deps_disable",
                "jsx_index_key",
            },
        ),
        (
            "typescript",
            "export async function POST(request: Request) {\n  const payload = await request.json();\n  return Response.json(payload);\n}\n'use client';\nconsole.log(process.env.DB_PASSWORD);\n",
            {"next_route_request_json", "next_client_secret_env"},
        ),
        (
            "javascript",
            "export async function POST(request) {\n  const payload = await request.json();\n  return Response.json(payload);\n}\n'use client';\nconsole.log(process.env.DB_PASSWORD);\n",
            {"next_route_request_json", "next_client_secret_env"},
        ),
        (
            "javascript",
            "const transform = new Function('payload', 'return payload.total');\ntransform(input);\n",
            {"function_constructor"},
        ),
        (
            "sql",
            "select * from users where id not in (select user_id from disabled_users) order by 1;\n",
            {"order_by_ordinal", "not_in_subquery"},
        ),
        (
            "yaml",
            "on:\n  pull_request_target:\nallowPrivilegeEscalation: true\nhostNetwork: true\nuses: actions/checkout@main\n",
            {
                "allow_privilege_escalation",
                "host_network_true",
                "uses_branch_ref",
                "github_actions_pull_request_target",
            },
        ),
        (
            "yaml",
            "services:\n  - postgres:latest\nscript:\n  - curl --insecure https://example.com/install.sh | bash\n",
            {"service_latest_tag", "ci_remote_bootstrap", "ci_insecure_download"},
        ),
        (
            "yaml",
            "api_key: prod-secret-token\n<<: *defaults\nadditionalProperties: true\ndefault: on\n",
            {"yaml_secret_literal", "yaml_merge_key", "yaml_additional_properties_true", "yaml_ambiguous_boolean_default"},
        ),
        (
            "dockerfile",
            "FROM python:latest AS runtime # keep runtime current\n",
            {"latest_tag"},
        ),
        (
            "dockerfile",
            "FROM python:3.12-slim AS runtime\n",
            {"base_tag_without_digest"},
        ),
        (
            "dockerfile",
            "USER 0\n",
            {"root_user"},
        ),
        (
            "dockerfile",
            "FROM golang:1.22-bookworm@sha256:1111111111111111111111111111111111111111111111111111111111111111 AS build\nFROM debian:bookworm-slim@sha256:2222222222222222222222222222222222222222222222222222222222222222 AS runtime\nCOPY --from=build --chown=10001:10001 /usr/local/ /usr/local/ # keep builder-installed runtime libs\n",
            {"copy_from_builder_usr_local"},
        ),
        (
            "dockerfile",
            "ADD https://example.com/install.sh /tmp/install.sh\nRUN curl https://example.com/install.sh | bash\n",
            {"add_remote_url", "curl_pipe_shell_run"},
        ),
        (
            "dockerfile",
            "ARG NPM_TOKEN\nENV PIP_INDEX_TOKEN=$NPM_TOKEN\n",
            {"build_secret_arg_env"},
        ),
        (
            "dockerfile",
            "ENV PIP_EXTRA_INDEX_URL=https://build-user:${PIP_PASSWORD}@packages.example.com/simple\n",
            {"build_secret_arg_env_authenticated_url"},
        ),
        (
            "dockerfile",
            "FROM debian:bookworm-slim@sha256:1111111111111111111111111111111111111111111111111111111111111111\nRUN apt-get update && apt-get install -y --no-install-recommends curl git\n",
            {"apt_get_install_unpinned"},
        ),
        (
            "sql",
            "select user_id, count(*) from events group by 1 limit 10;\n",
            {"group_by_ordinal", "limit_without_order"},
        ),
        (
            "sql",
            "select * from {{ ref('events') }};\n{{ run_query(\"vacuum analytics.events\") }}\ndrop table legacy_users cascade;\nalter table accounts drop column legacy_flag;\nalter table orders alter column status set not null;\ncreate index idx_orders_created_at on orders(created_at);\n",
            {
                "dbt_select_star_ref",
                "dbt_run_query",
                "migration_drop_table",
                "migration_drop_cascade",
                "migration_drop_column",
                "migration_set_not_null",
                "migration_create_index_plain",
            },
        ),
    ],
)
def test_query_analysis_detects_multilang_patterns(
    language_id: str,
    code: str,
    expected_patterns: set[str],
) -> None:
    analysis = build_query_analysis(code, input_kind="code", language_id=language_id)
    names = {pattern.name for pattern in analysis.patterns}

    assert expected_patterns <= names


def test_go_errors_is_does_not_trigger_direct_sentinel_compare_pattern() -> None:
    analysis = build_query_analysis(
        "if errors.Is(readErr, fs.ErrNotExist) {\n    return nil\n}\n",
        input_kind="code",
        language_id="go",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "sentinel_error_compare" not in names


def test_typescript_void_fetch_with_local_catch_does_not_trigger_detached_pattern() -> None:
    analysis = build_query_analysis(
        "void fetch('/api/audit').catch(reportDetachedFailure);\n",
        input_kind="code",
        language_id="typescript",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "void_fetch_call" not in names


def test_go_http_client_timeout_and_body_close_do_not_trigger_when_visible() -> None:
    analysis = build_query_analysis(
        "func fetch(url string) ([]byte, error) {\n"
        "    client := &http.Client{Timeout: 5 * time.Second}\n"
        "    resp, err := client.Get(url)\n"
        "    if err != nil {\n"
        "        return nil, err\n"
        "    }\n"
        "    defer resp.Body.Close()\n"
        "    return io.ReadAll(resp.Body)\n"
        "}\n",
        input_kind="code",
        language_id="go",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "http_client_without_timeout" not in names
    assert "http_response_body_without_close" not in names


def test_dockerfile_safe_index_url_does_not_trigger_authenticated_secret_pattern() -> None:
    analysis = build_query_analysis(
        "ENV PIP_EXTRA_INDEX_URL=https://packages.example.com/simple\n",
        input_kind="code",
        language_id="dockerfile",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "build_secret_arg_env" not in names
    assert "build_secret_arg_env_authenticated_url" not in names


def test_bash_mktemp_with_trap_does_not_trigger_cleanup_pattern() -> None:
    analysis = build_query_analysis(
        "#!/usr/bin/env bash\n"
        "tmp_file=$(mktemp)\n"
        "trap 'rm -f \"$tmp_file\"' EXIT\n"
        "printf '%s\\n' \"$payload\" > \"$tmp_file\"\n",
        input_kind="code",
        language_id="bash",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "mktemp_without_trap" not in names


def test_dockerfile_pinned_apt_install_does_not_trigger_unpinned_package_pattern() -> None:
    analysis = build_query_analysis(
        "RUN apt-get update && apt-get install -y --no-install-recommends "
        "curl=7.88.1-10+deb12u8 git=1:2.39.5-0+deb12u2\n",
        input_kind="code",
        language_id="dockerfile",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "apt_get_install_unpinned" not in names


def test_dockerfile_non_root_numeric_user_does_not_trigger_root_pattern() -> None:
    analysis = build_query_analysis(
        "USER 10001\n",
        input_kind="code",
        language_id="dockerfile",
    )
    names = {pattern.name for pattern in analysis.patterns}

    assert "root_user" not in names


def test_dockerfile_digestless_base_with_inline_comment_triggers_without_matching_digest_pinned_variant() -> None:
    digestless = build_query_analysis(
        "FROM python:3.12-slim AS runtime # official runtime base\n",
        input_kind="code",
        language_id="dockerfile",
    )
    digestless_names = {pattern.name for pattern in digestless.patterns}

    digest_pinned = build_query_analysis(
        "FROM python:3.12-slim@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef AS runtime # official runtime base\n",
        input_kind="code",
        language_id="dockerfile",
    )
    digest_pinned_names = {pattern.name for pattern in digest_pinned.patterns}

    assert "base_tag_without_digest" in digestless_names
    assert "base_tag_without_digest" not in digest_pinned_names


def test_dockerfile_latest_tag_with_alias_and_comment_triggers_without_matching_digest_pinned_variant() -> None:
    digestless = build_query_analysis(
        "FROM python:latest AS runtime # official runtime base\n",
        input_kind="code",
        language_id="dockerfile",
    )
    digestless_names = {pattern.name for pattern in digestless.patterns}

    digest_pinned = build_query_analysis(
        "FROM python:latest@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef AS runtime # official runtime base\n",
        input_kind="code",
        language_id="dockerfile",
    )
    digest_pinned_names = {pattern.name for pattern in digest_pinned.patterns}

    assert "latest_tag" in digestless_names
    assert "latest_tag" not in digest_pinned_names
