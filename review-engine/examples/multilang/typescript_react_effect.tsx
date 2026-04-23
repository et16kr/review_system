import { useEffect } from "react";

type Props = {
  url: string;
  html: string;
};

export function AuditPanel({ url, html }: Props) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(async () => {
    const response = await fetch(url);
    await response.text();
  }, []);

  return <section dangerouslySetInnerHTML={{ __html: html }} />;
}
