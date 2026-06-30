import type { Preview } from "@storybook/react";
import "../src/styles/tokens.css";
import "../src/styles/base.css";
import "../src/components/components.css";

const preview: Preview = {
  parameters: {
    layout: "padded",
    backgrounds: {
      default: "Surface",
      values: [
        { name: "Surface", value: "#ffffff" },
        { name: "Mint Wash", value: "#e8f6f1" },
        { name: "Deep Ink", value: "#0e1f2a" }
      ]
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i
      }
    }
  }
};

export default preview;
