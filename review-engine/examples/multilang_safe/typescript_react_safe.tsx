import { useEffect, useState } from "react";

type Props = {
  url: string;
};

export function AuditPanel({ url }: Props) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const response = await fetch(url);
      if (!cancelled && response.ok) {
        setCount(1);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [url]);

  return <section>{count}</section>;
}
