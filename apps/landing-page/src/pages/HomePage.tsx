import { Hero } from "../sections/Hero";
import { TrustStrip } from "../sections/TrustStrip";
import { Pillars } from "../sections/Pillars";
import { Lifecycle } from "../sections/Lifecycle";
import { Recovery } from "../sections/Recovery";
import { Developers } from "../sections/Developers";
import { Portal } from "../sections/Portal";
import { BuiltFor } from "../sections/BuiltFor";
import { FAQ } from "../sections/FAQ";
import { CTA } from "../sections/CTA";

export function HomePage() {
  return (
    <>
      <Hero />
      <TrustStrip />
      <Pillars />
      <Lifecycle />
      <Recovery />
      <Developers />
      <Portal />
      <BuiltFor />
      <FAQ />
      <CTA />
    </>
  );
}
