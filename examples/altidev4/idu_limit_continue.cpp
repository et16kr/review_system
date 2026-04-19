/*
Source excerpt:
- /home/et16/work/altidev4/tsrc/id/iduLimitTest/iduLimitTest.cpp
- lines: 110-155
*/

    return IDE_SUCCESS;
}

IDE_RC StartThread()
{
    SInt  i;

    for(i = 0; i < IDU_TEST_THREAD_COUNT; i ++)
    {
        if(gThreadExist[i] == ID_FALSE)
        {
            continue;
        }

        IDE_TEST(gThread[i].start() != IDE_SUCCESS);

        idlOS::printf("Thread [%"ID_INT32_FMT"] Created Successfully!\n", i);
    }

    for(i = 0; i < IDU_TEST_THREAD_COUNT; i ++)
    {
        if(gThreadExist[i] == ID_FALSE)
        {
            continue;
        }

        IDE_TEST(gThread[i].waitToStart() != IDE_SUCCESS);

        idlOS::printf("Thread [%"ID_INT32_FMT"] Started Successfully!\n", i);
    }
    idlOS::printf("ALL Thread Start Success!\n");

    return IDE_SUCCESS;

    IDE_EXCEPTION_END;

    idlOS::printf("[ERROR] Thread Initialized FAIL\n");

    return IDE_FAILURE;
}

IDE_RC StopThread()
{
    SInt  i;

    for(i = 0; i < IDU_TEST_THREAD_COUNT; i ++)
