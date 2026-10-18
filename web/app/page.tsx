import data from "../public/data/seed1.json";
import Replay, { type Seed } from "@/components/Replay";

export default function Page() {
  return <Replay data={data as Seed} />;
}
