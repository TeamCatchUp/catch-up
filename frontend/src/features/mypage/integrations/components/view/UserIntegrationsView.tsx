import ConnectedAccountsUserSection from '../account/sections/ConnectedAccountsUserSection';

/** 일반 사용자 협업툴 연동 화면 */
export default function UserIntegrationsView() {
  return (
    <section className="mx-auto flex w-full flex-col gap-6 px-16 pt-9 pb-30 min-[1440px]:max-w-282">
      <h1 className="text-heading-xlarge text-content-normal">협업툴 연동</h1>
      <div className="border-edge-neutral h-px w-full border-b" />
      <ConnectedAccountsUserSection />
    </section>
  );
}
