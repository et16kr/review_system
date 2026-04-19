/*
Source excerpt:
- /home/et16/work/altidev4/src/rp/rps/rpsSmExecutor.cpp
- lines: 145-185
*/

            if(sMaxRowSize < sRowSize)
            {
                sMaxRowSize = sRowSize;
            }
        }
    }

    if(sMaxRowSize > 0)
    {
        sMaxRowSize = idlOS::align(sMaxRowSize, 8);
        IDE_TEST_RAISE(iduMemMgr::malloc(IDU_MEM_RP_RPS,
                                         sMaxRowSize,
                                         (void **)&mRealRow,
                                         IDU_MEM_IMMEDIATE)
                       != IDE_SUCCESS, ERR_MEMORY_ALLOC_REAL_ROW);
        mRealRowSize = sMaxRowSize;
    }

    return IDE_SUCCESS;

    IDE_EXCEPTION(ERR_MEMORY_ALLOC_REAL_ROW);
    {
        IDE_ERRLOG(IDE_RP_0);
        IDE_SET(ideSetErrorCode(rpERR_ABORT_MEMORY_ALLOC,
                                "rpsSmExecutor::initialize",
                                "mRealRow"));
    }
    IDE_EXCEPTION_END;
    IDE_PUSH();

    if(mRealRow != NULL)
    {
        (void)iduMemMgr::free(mRealRow);
        mRealRow = NULL;
    }

    IDE_POP();
    return IDE_FAILURE;
}

void rpsSmExecutor::destroy()
