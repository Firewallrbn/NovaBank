import SiteNav from '../components/SiteNav';
import Hero from '../sections/Hero';
import SagaFlow from '../sections/SagaFlow';
import Modes from '../sections/Modes';
import TestCases from '../sections/TestCases';
import Observability from '../sections/Observability';
import SiteFooter from '../sections/SiteFooter';

export default function Landing() {
  return (
    <div className="min-h-[100dvh] bg-ink-900">
      <SiteNav />
      <main>
        <Hero />
        <SagaFlow />
        <Modes />
        <TestCases />
        <Observability />
      </main>
      <SiteFooter />
    </div>
  );
}
