IDE_RC smpWork(void)
{
    IDE_RC rc;

    rc = smpChild();
    if (rc != IDE_SUCCESS)
    {
        return IDE_FAILURE;
    }

    return IDE_SUCCESS;
}
