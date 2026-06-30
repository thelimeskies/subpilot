import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Modal } from "../components/Modal";
import { Sheet } from "../components/Sheet";
import { Button } from "../components/Button";
import { Field, TextInput } from "../components/Form";

const meta: Meta = {
  title: "Overlays/Modal and Sheet",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const ConfirmationModal: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <>
        <Button onClick={() => setOpen(true)}>Open modal</Button>
        <Modal
          open={open}
          onClose={() => setOpen(false)}
          title="Cancel subscription?"
          description="The customer will keep access until the end of the current period."
          footer={
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Keep active
              </Button>
              <Button variant="danger" onClick={() => setOpen(false)}>
                Cancel subscription
              </Button>
            </>
          }
        >
          <p>
            Acme Learning Hub will stop renewing on July 12. Outstanding invoices stay in
            recovery until paid.
          </p>
        </Modal>
      </>
    );
  }
};

export const EditSheet: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <>
        <Button onClick={() => setOpen(true)}>Open sheet</Button>
        <Sheet
          open={open}
          onClose={() => setOpen(false)}
          title="Edit plan"
          description="Changes apply to new subscriptions only."
          footer={
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Discard
              </Button>
              <Button onClick={() => setOpen(false)}>Save</Button>
            </>
          }
        >
          <div style={{ display: "grid", gap: 16 }}>
            <Field label="Plan name">
              <TextInput defaultValue="Growth Monthly" />
            </Field>
            <Field label="Amount" hint="Charged every billing cycle.">
              <TextInput defaultValue="24000" />
            </Field>
          </div>
        </Sheet>
      </>
    );
  }
};
