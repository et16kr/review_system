# 저장소 스캔 보고서

- 루트: `/home/et16/work/altidev4`
- 스캔한 파일 수: 5297
- 매치된 파일 수: 2799

## 주요 패턴

- `primitive_format_specifier`: 1157
- `ide_rc_flow`: 1006
- `direct_system_call`: 930
- `malloc_free`: 576
- `raw_new`: 470
- `continue_usage`: 347
- `manual_delete`: 307
- `manual_lock_unlock`: 267
- `direct_system_header`: 212
- `switch_without_default`: 94
- `free_without_null_reset`: 37
- `for_initializer_declaration`: 12

## 주요 파일

- `/home/et16/work/altidev4/src/ul/ulp/ulpCompl.cpp` | 점수=6.35 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, continue_usage
- `/home/et16/work/altidev4/tsrc/id/windump/mydump.cpp` | 점수=6.35 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/ul/ulp/ulpPreprocl.cpp` | 점수=6.35 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, continue_usage
- `/home/et16/work/altidev4/tsrc/id/windump/StackWalker.cpp` | 점수=6.35 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, continue_usage
- `/home/et16/work/altidev4/ut/iloader3/src/iloCommandLexer.cpp` | 점수=6.35 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smx/smxTrans.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smc/smcTable.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/qp/qdn/qdnTrigger.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/rp/rpc/rpcManager.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smx/smxTransMgr.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/rp/rpx/rpxReceiver.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sd/sdi/sdiZookeeper.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smp/smpVarPageList.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/sdn/sdnb/sdnbModule.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smn/smnb/smnbModule.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/st/stn/stndr/stndrModule.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smr/smrLogMultiplexThread.cpp` | 점수=6.30 | 패턴 수=7 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/pd/pdl/OS.cpp` | 점수=6.20 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_call, continue_usage, for_initializer_declaration
- `/home/et16/work/altidev4/src/id/idl/idl.cpp` | 점수=6.20 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_call, continue_usage, for_initializer_declaration
- `/home/et16/work/altidev4/src/pd/pdl/PDL2.cpp` | 점수=6.20 | 패턴 수=7 | raw_new, malloc_free, manual_delete, direct_system_call, continue_usage, for_initializer_declaration
- `/home/et16/work/altidev4/src/sm/smr/smrLogFileMgr.cpp` | 점수=6.00 | 패턴 수=7 | raw_new, malloc_free, manual_lock_unlock, direct_system_call, continue_usage, switch_without_default
- `/home/et16/work/altidev4/tsrc/id/iduQueue/iduQueuePerf.cpp` | 점수=5.55 | 패턴 수=6 | raw_new, malloc_free, free_without_null_reset, manual_delete, direct_system_call, ide_rc_flow
- `/home/et16/work/altidev4/src/sd/sdp/sdpjl.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/qp/qcp/qcphl.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/qp/qcp/qcpll.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/mt/mtcd/mtcddl.c` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/mt/mtd/mtddl.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/dk/dkc/dkcLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/isql/src/iSQLLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/isql/src/iSQLPreLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/ul/ulp/ulpPreprocifl.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/isql/src/iSQLScanLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/altiWrap/src/altiWraplp.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/altiWrap/src/altiWrapll.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/isql/src/iSQLParamLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/iloader3/src/iloFormLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/ut/isql/src/iSQLConnectLexer.cpp` | 점수=5.53 | 패턴 수=6 | raw_new, malloc_free, manual_delete, direct_system_header, direct_system_call, primitive_format_specifier
- `/home/et16/work/altidev4/src/sm/sma/smaLogicalAger.cpp` | 점수=5.52 | 패턴 수=6 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/sma/smaDeleteThread.cpp` | 점수=5.52 | 패턴 수=6 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, continue_usage
- `/home/et16/work/altidev4/src/sm/smr/smrLogMgr.cpp` | 점수=5.48 | 패턴 수=6 | raw_new, malloc_free, manual_delete, manual_lock_unlock, direct_system_call, primitive_format_specifier
