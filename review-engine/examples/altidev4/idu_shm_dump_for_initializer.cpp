/*
Source excerpt:
- /home/et16/work/altidev4/src/id/idu/iduShmDump.cpp
- lines: 145-205
*/

    sWrittenBytes += idlOS::snprintf( aMsgBuf + sWrittenBytes,
                                      aBufSize - sWrittenBytes,
                                      "mSegCount: %"ID_vULONG_FMT" \n",
                                      sSSegment->mSegCount );

    for( UInt i = 0 ; i < sSSegment->mSegCount ; i++ )
    {
        sWrittenBytes += getMsgStShmSegInfo( aMsgBuf + sWrittenBytes,
                                             aBufSize - sWrittenBytes,
                                             i );
    }

    IDE_TEST_RAISE( sWrittenBytes >= (aBufSize  - 1),
                    err_textbuf_insufficient );

    return IDE_SUCCESS;

    IDE_EXCEPTION( err_textbuf_insufficient );
    {
        idlOS::printf( "%s (Current Text Buffer Length : %"ID_UINT32_FMT")\n",
                       mErrTextBufInsufficient,
                       aBufSize );
    }

    IDE_EXCEPTION_END;

    return IDE_FAILURE;
}

IDE_RC iduShmDump::getMsgMatrix( SChar * aMsgBuf, UInt aBufSize )
{
    UInt             sWrittenBytes = 0;
    iduShmSSegment * sSSegment;

    sSSegment = iduShmMgr::mSSegment;

    /// 이 코드 아래로는 iduShmMgr으로부터 정보를 가져오지 않는다.
    /////////////////////////////////////////////////////////////////////////////


    sWrittenBytes += idlOS::snprintf( aMsgBuf + sWrittenBytes,
                                      aBufSize - sWrittenBytes,
                                      "---- Matrix View ---- \n" );
    UInt sFstMask = 1;
    UInt sSndMask = 1;

    for( UInt i = 0 ; i < IDU_SHM_FST_LVL_INDEX_COUNT ; i++ )
    {
        sWrittenBytes +=
            idlOS::snprintf( aMsgBuf + sWrittenBytes,
                             aBufSize - sWrittenBytes,
                             "%c | ",
                             sSSegment->mFstLvlBitmap & sFstMask ? '1' : '0' );

        sSndMask = 1;

        for( UInt j = 0 ; j < IDU_SHM_SND_LVL_INDEX_COUNT ; j++ )
        {
            sWrittenBytes +=
                idlOS::snprintf( aMsgBuf + sWrittenBytes,
                                 aBufSize - sWrittenBytes,
