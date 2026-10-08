import { Config } from "@remotion/cli/config";

Config.setChromiumOpenGlRenderer("angle");
Config.setChromiumDisableWebSecurity(true);
Config.setConcurrency(4);
