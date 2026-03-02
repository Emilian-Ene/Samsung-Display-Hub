<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import ConfirmDialog from 'primevue/confirmdialog';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Select from 'primevue/select';
import Slider from 'primevue/slider';
import Tag from 'primevue/tag';
import Toast from 'primevue/toast';
import Toolbar from 'primevue/toolbar';
import { useConfirm } from 'primevue/useconfirm';
import { useToast } from 'primevue/usetoast';

const API_BASE =
  import.meta.env.VITE_API_URL || 'https://samsung-display-hub.onrender.com';
const defaultTvIp = import.meta.env.VITE_DEFAULT_TV_IP || '192.168.1.122';
const defaultDisplayId = import.meta.env.VITE_DEFAULT_DISPLAY_ID || '1';
const defaultPort = import.meta.env.VITE_DEFAULT_PORT || '1515';
const defaultProtocol = import.meta.env.VITE_DEFAULT_PROTOCOL || 'SIGNAGE_MDC';
const cloudApiKey = import.meta.env.VITE_CLOUD_API_KEY || '';
const STORAGE_KEY = 'samsung-admin-devices-v1';
const LOGS_STORAGE_KEY = 'samsung-admin-logs-v1';
const BULK_REFRESH_CONCURRENCY = 8;
const AGENT_STATUS_REFRESH_INTERVAL_MS = 15000;
const AGENT_ONLINE_THRESHOLD_MS = 45000;
const IMPORTANT_TOAST_SEVERITIES = new Set(['warn', 'error']);
const BRAND_LOGO_URL = '/logo.jpg';
const confirm = useConfirm();
const toast = useToast();

const currentView = ref('dashboard');
const selectedDeviceId = ref(null);

const devices = ref([]);
const appStatus = ref('Ready');
const commandLogs = ref([]);
const showBrandLogo = ref(true);
const agentStatusById = ref({});
const agentsLastUpdatedAt = ref('-');
let agentStatusRefreshInterval = null;

const mdcCommands = ref([]);
const selectedMdcCommand = ref('status');
const mdcOperation = ref('auto');
const mdcArgsText = ref('');

const addName = ref('');
const addIp = ref('');
const addPort = ref('');
const addDisplayId = ref('');
const addProtocol = ref('AUTO');
const addAgentId = ref('');
const addSite = ref('');
const addCity = ref('');
const addZone = ref('');
const addArea = ref('');
const addDescription = ref('');
const csvFileInput = ref(null);
const deviceSearch = ref('');
const statusFilter = ref('all');
const siteFilter = ref('all');
const cityFilter = ref('all');
const sortBy = ref('name');
const sortDirection = ref('asc');
const selectedDeviceRows = ref([]);
const isDeviceTestBusy = ref(false);
const isPowerBusy = ref(false);
const isMdcBusy = ref(false);
const isAgentRefreshBusy = ref(false);
const volumeLevel = ref(50);
const brightnessLevel = ref(50);
const isCommandInfoOpen = ref(false);

const PROTOCOL_SIGNAGE_MDC = 'SIGNAGE_MDC';
const protocolOptions = [
  { label: 'AUTO', value: 'AUTO' },
  { label: 'MDC', value: PROTOCOL_SIGNAGE_MDC },
];
const statusFilterOptions = [
  { label: 'All statuses', value: 'all' },
  { label: 'Online', value: 'online' },
  { label: 'Offline', value: 'offline' },
  { label: 'Unknown', value: 'unknown' },
];
const mdcOperationOptions = ['auto', 'get', 'set'];

const selectedDevice = computed(() => {
  return (
    devices.value.find((device) => device.id === selectedDeviceId.value) || null
  );
});

const currentViewTitle = computed(() => {
  if (currentView.value === 'agents') {
    return 'Explore Agents';
  }

  if (currentView.value === 'device') {
    return 'Device Control';
  }

  return 'Dashboard';
});

const selectedCommandMeta = computed(() => {
  return (
    mdcCommands.value.find((item) => item.name === selectedMdcCommand.value) ||
    null
  );
});

const selectedMdcFields = computed(() => {
  return Array.isArray(selectedCommandMeta.value?.fields)
    ? selectedCommandMeta.value.fields
    : [];
});

const mdcCommandLabelOverrides = {
  dst: 'Daylight Saving Time',
  manual_lamp: 'Backlight Intensity',
  auto_lamp: 'Auto Backlight Schedule',
  clock_m: 'Clock (Minute Precision)',
  clock_s: 'Clock (Second Precision)',
  weekly_restart: 'Weekly Restart Schedule',
  panel_on_time: 'Panel On Time',
  virtual_remote: 'Remote Key Command',
  set_content_download: 'Content Download URL',
};

const mdcUppercaseTokens = new Set([
  'mdc',
  'osd',
  'rgb',
  'ir',
  'id',
  'tv',
  'pip',
  'url',
  'api',
  'ip',
]);

const mdcCommandLabel = (commandName) => {
  const name = String(commandName || '').trim();
  if (!name) {
    return '';
  }

  if (Object.hasOwn(mdcCommandLabelOverrides, name)) {
    return mdcCommandLabelOverrides[name];
  }

  return name
    .split('_')
    .map((part) => {
      const lower = String(part || '').toLowerCase();
      if (mdcUppercaseTokens.has(lower)) {
        return lower.toUpperCase();
      }
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
};

const mdcCommandOptions = computed(() =>
  mdcCommands.value.map((command) => ({
    ...command,
    label: mdcCommandLabel(command.name),
  })),
);

const commandHelpCatalog = {
  status: {
    description:
      'Gets key device state in one call: power, volume, mute, input, picture aspect, and timer flags.',
    notes: [
      'On no-audio models, volume/mute may return 255.',
      'N_TIME_NF and F_TIME_NF are legacy timer flags and are often 0.',
    ],
  },
  video: {
    description:
      'Gets grouped picture values (contrast, brightness, sharpness, color, tint, tone, and temperature).',
  },
  rgb: {
    description:
      'Gets RGB mode picture values including RGB gain levels and tone/temperature.',
  },
  serial_number: {
    description: 'Reads the hardware serial number reported by the display.',
  },
  error_status: {
    description:
      'Reads lamp/temperature/fan/input error indicators for quick diagnostics.',
  },
  software_version: {
    description: 'Reads installed firmware/software version string.',
  },
  model_number: {
    description:
      'Reads model species/code and whether TV features are supported on this unit.',
  },
  power: {
    description: 'Gets or sets power state (OFF, ON, REBOOT).',
    notes: ['Use ON then wait for boot before running dependent commands.'],
  },
  volume: {
    description: 'Gets or sets volume level from 0 to 100.',
  },
  mute: {
    description: 'Gets or sets mute state (OFF, ON, NONE).',
  },
  input_source: {
    description: 'Gets or changes active input source.',
    notes: [
      'Some sources are model-dependent and may NAK on unsupported devices.',
      'PC variants (example HDMI1_PC) are often get-only.',
    ],
  },
  picture_aspect: {
    description: 'Gets or sets screen picture aspect mode.',
    notes: [
      'Often unavailable when video wall state is ON.',
      'Available modes depend on source signal and model.',
    ],
  },
  screen_mode: {
    description:
      'Gets or sets high-level screen mode (16:9, zoom, 4:3, wide zoom).',
  },
  screen_size: {
    description: 'Reads configured screen size in inches.',
  },
  network_configuration: {
    description:
      'Gets or sets static network details (IP, subnet, gateway, DNS).',
  },
  network_mode: {
    description: 'Gets or sets network mode (DYNAMIC or STATIC).',
  },
  network_ap_config: {
    description: 'Stores Wi-Fi SSID/password profile on supported models.',
    notes: ['Applying this may change network path and interrupt response.'],
  },
  weekly_restart: {
    description:
      'Gets or sets weekly auto-restart schedule by weekday and time.',
    formats: [
      'SET args order: WEEKDAY, TIME',
      'TIME format: HH:MM (example: 03:30)',
      'Example: MON,TUE,WED,03:30',
    ],
  },
  magicinfo_channel: {
    description: 'Sets MagicInfo direct channel number.',
  },
  magicinfo_server: {
    description: 'Gets or sets MagicInfo server URL.',
  },
  magicinfo_content_orientation: {
    description: 'Gets or sets orientation mode for MagicInfo content.',
  },
  mdc_connection: {
    description: 'Gets or sets MDC transport type (RS232C or RJ45).',
    notes: ['Setting RJ45 may disable serial MDC on some products.'],
  },
  contrast: {
    description: 'Gets or sets picture contrast (0-100).',
  },
  brightness: {
    description: 'Gets or sets panel brightness (0-100).',
  },
  sharpness: {
    description: 'Gets or sets sharpness (0-100).',
  },
  color: {
    description: 'Gets or sets color saturation (0-100).',
  },
  tint: {
    description: 'Gets or sets tint balance (0-100).',
    notes: ['Commonly accepted in steps of 2 on many models.'],
  },
  h_position: {
    description: 'Moves image horizontal position (LEFT or RIGHT).',
  },
  v_position: {
    description: 'Moves image vertical position (UP or DOWN).',
  },
  auto_power: {
    description: 'Gets or sets auto power behavior (OFF or ON).',
  },
  clear_menu: {
    description: 'Clears OSD/menu overlays from the screen.',
  },
  ir_state: {
    description: 'Gets or sets infrared remote receiver enable state.',
    notes: ['May operate even when device power is OFF, model-dependent.'],
  },
  rgb_contrast: {
    description: 'Gets or sets RGB contrast (0-100).',
  },
  rgb_brightness: {
    description: 'Gets or sets RGB brightness (0-100).',
  },
  auto_adjustment_on: {
    description: 'Triggers automatic image adjustment routine.',
  },
  color_tone: {
    description: 'Gets or sets color tone preset (cool/normal/warm/off).',
  },
  color_temperature: {
    description: 'Gets or sets color temperature (hectoKelvin).',
    notes: ['Typical supported values include 28, 30, 35 ... 160.'],
  },
  standby: {
    description: 'Gets or sets standby behavior (OFF, ON, AUTO).',
  },
  auto_lamp: {
    description: 'Gets or sets backlight auto-lamp schedule and values.',
    notes: ['Enabling manual lamp may turn auto lamp off.'],
    formats: [
      'SET args order: MAX_TIME, MAX_LAMP_VALUE, MIN_TIME, MIN_LAMP_VALUE',
      'Time format: HH:MM',
      'Example: 09:00,90,21:00,30',
    ],
  },
  manual_lamp: {
    description: 'Gets or sets manual backlight level.',
    notes: ['Enabling auto lamp may turn manual lamp off.'],
  },
  inverse: {
    description: 'Gets or sets inverse display mode.',
  },
  video_wall_mode: {
    description: 'Gets or sets video wall scaling mode (NATURAL or FULL).',
    notes: ['Requires video wall state ON.'],
  },
  safety_lock: {
    description: 'Gets or sets safety lock state.',
  },
  panel_lock: {
    description: 'Gets or sets panel key lock state.',
  },
  channel_change: {
    description: 'Changes channel one step UP or DOWN.',
  },
  volume_change: {
    description: 'Changes volume one step UP or DOWN.',
  },
  ticker: {
    description: 'Gets or sets on-screen ticker text and animation parameters.',
    notes: [
      'POS_HORIZ/POS_VERTI may return NONE when unsupported.',
      'Best for short operational messages and signage overlays.',
    ],
  },
  device_name: {
    description: 'Gets or sets the network-visible device name.',
  },
  osd: {
    description: 'Gets or sets overall OSD enable state.',
  },
  picture_mode: {
    description: 'Gets or sets picture preset mode.',
  },
  sound_mode: {
    description: 'Gets or sets sound preset mode.',
  },
  all_keys_lock: {
    description: 'Gets or sets both remote and panel key lock state.',
    notes: ['Can commonly operate regardless of power state.'],
  },
  panel_on_time: {
    description: 'Reads total panel-on runtime in 10-minute units.',
    notes: ['Hours can be estimated as MIN10 / 6.'],
  },
  video_wall_state: {
    description: 'Gets or sets whether video wall mode is enabled.',
  },
  video_wall_model: {
    description:
      'Gets or sets video wall matrix size and panel serial position.',
    notes: ['Requires video wall state ON.'],
  },
  model_name: {
    description: 'Reads human-readable model name string.',
  },
  energy_saving: {
    description: 'Gets or sets energy-saving profile.',
  },
  reset: {
    description: 'Resets selected settings group (picture/sound/setup/all).',
    notes: ['Use ALL with caution.'],
  },
  osd_type: {
    description: 'Gets or sets OSD visibility per message type.',
  },
  timer_13: {
    description: 'Legacy integrated timer command format (13-length variant).',
    notes: ['Older models feature; newer devices may require timer_15.'],
    formats: [
      'SET starts with TIMER_ID, then timer values',
      'ON_TIME/OFF_TIME format: HH:MM',
      'Example start: 1,08:00,true,18:00,true,...',
    ],
  },
  timer_15: {
    description: 'Integrated timer command format for newer models.',
    notes: ['Older models may not support this format.'],
    formats: [
      'SET starts with TIMER_ID, then timer values',
      'ON_TIME/OFF_TIME format: HH:MM',
      'Example start: 1,08:00,true,18:00,true,...',
    ],
  },
  clock_m: {
    description: 'Gets or sets device clock (minute precision).',
    notes: ['Intended for models developed until 2013.'],
    formats: [
      'DATETIME format: YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM',
      'Example: 2026-02-10T18:20',
    ],
  },
  holiday_set: {
    description: 'Adds/deletes holiday schedule windows.',
    notes: ['For DELETE_ALL, all date fields should be zeroed.'],
  },
  holiday_get: {
    description: 'Reads holiday schedule or count by optional index.',
  },
  virtual_remote: {
    description: 'Sends virtual remote key codes through MDC.',
    notes: [
      'Useful for menu navigation flows where direct command is missing.',
    ],
  },
  network_standby: {
    description: 'Gets or sets network standby state.',
  },
  dst: {
    description: 'Gets or sets DST schedule and offset rules.',
    formats: [
      'SET args order: DST_STATE, START_MONTH, START_WEEK, START_WEEKDAY, START_TIME, END_MONTH, END_WEEK, END_WEEKDAY, END_TIME, OFFSET',
      'START_TIME/END_TIME format: HH:MM',
      'Example: MANUAL,MAR,WEEK_LAST,SUN,02:00,OCT,WEEK_LAST,SUN,03:00,PLUS_1_00',
    ],
  },
  auto_id_setting: {
    description: 'Starts or ends auto ID assignment mode.',
  },
  display_id: {
    description: 'Gets or sets display ID visibility state.',
  },
  clock_s: {
    description: 'Gets or sets device clock (second precision).',
    notes: ['Intended for models developed after 2013.'],
    formats: [
      'DATETIME format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS',
      'Example: 2026-02-10T18:20:00',
    ],
  },
  set_content_download: {
    description:
      'Sets content server URL for remote content download workflows.',
    notes: [
      'Requires network connectivity and model support.',
      'Common usage points to content manifest URL.',
    ],
  },
  launcher_play_via: {
    description: 'Gets or sets launcher playback source mode.',
  },
  launcher_url_address: {
    description: 'Gets or sets launcher URL address.',
  },
  osd_menu_orientation: {
    description: 'Gets or sets OSD menu orientation mode.',
  },
  osd_source_content_orientation: {
    description: 'Gets or sets source content orientation mode.',
  },
  osd_aspect_ratio: {
    description: 'Gets or sets portrait-mode OSD aspect behavior.',
  },
  osd_pip_orientation: {
    description: 'Gets or sets OSD PIP orientation mode.',
  },
  osd_menu_size: {
    description: 'Gets or sets OSD menu size profile.',
  },
  auto_source_switch: {
    description: 'Gets or sets automatic source switching state.',
  },
  auto_source: {
    description: 'Gets or sets primary/secondary auto-source fallback rules.',
  },
  panel: {
    description: 'Gets or sets panel state (ON/OFF).',
  },
  screen_mute: {
    description: 'Gets or sets screen mute (video output blanking).',
  },
  script: {
    description: 'Runs multi-command script file with retry/sleep options.',
    notes: [
      'Command order is preserved per device.',
      'Use sleep steps for virtual_remote-heavy scripts.',
    ],
  },
  raw: {
    description: 'Sends low-level raw command payload for testing/debugging.',
  },
};

const selectedCommandHelp = computed(() => {
  const name = selectedMdcCommand.value;
  if (!name) {
    return 'Select a command to view details.';
  }

  const item = commandHelpCatalog[name];
  if (item?.description) {
    return item.description;
  }

  const autoMode =
    selectedCommandMeta.value?.supports_get &&
    selectedCommandMeta.value?.supports_set
      ? 'supports GET and SET'
      : selectedCommandMeta.value?.supports_get
        ? 'supports GET'
        : selectedCommandMeta.value?.supports_set
          ? 'supports SET'
          : 'is available';

  const fieldCount = selectedMdcFields.value.length;
  const fieldSummary = fieldCount
    ? ` with ${fieldCount} argument${fieldCount === 1 ? '' : 's'}`
    : ' with no required arguments';

  return `No custom description yet. This command ${autoMode}${fieldSummary}.`;
});

const selectedCommandNotes = computed(() => {
  const name = selectedMdcCommand.value;
  if (!name) {
    return [];
  }
  return commandHelpCatalog[name]?.notes || [];
});

const selectedCommandFormats = computed(() => {
  const name = selectedMdcCommand.value;
  if (!name) {
    return [];
  }
  return commandHelpCatalog[name]?.formats || [];
});

const selectedCommandExample = computed(() => {
  const name = selectedMdcCommand.value;
  if (!name) {
    return '-';
  }

  const fieldExample = selectedMdcFields.value
    .map((field) => {
      if (Array.isArray(field.enum) && field.enum.length) {
        return String(field.enum[0]);
      }
      if (field.range && Number.isFinite(field.range.min)) {
        return String(field.range.min);
      }
      return 'value';
    })
    .join(', ');

  const friendlyName = mdcCommandLabel(name);
  const commandPrefix = `${friendlyName} (${name})`;

  return fieldExample.length
    ? `${commandPrefix} ${fieldExample}`
    : `${commandPrefix}`;
});

const selectedDeviceCount = computed(() => selectedDeviceRows.value.length);

const uniqueFieldValues = (fieldName) =>
  computed(() => {
    const set = new Set(
      devices.value
        .map((device) => String(device[fieldName] || '').trim())
        .filter((value) => value.length > 0),
    );

    return [...set].sort((left, right) => left.localeCompare(right));
  });

const siteOptions = uniqueFieldValues('site');
const cityOptions = uniqueFieldValues('city');
const siteFilterItems = computed(() => [
  { label: 'All sites', value: 'all' },
  ...siteOptions.value.map((value) => ({ label: value, value })),
]);
const cityFilterItems = computed(() => [
  { label: 'All cities', value: 'all' },
  ...cityOptions.value.map((value) => ({ label: value, value })),
]);

const trackedAgentRows = computed(() => {
  const ids = [
    ...new Set(
      devices.value
        .map((device) => String(device?.agentId || '').trim())
        .filter((value) => value.length > 0),
    ),
  ].sort((left, right) => left.localeCompare(right));

  return ids.map((agentId) => {
    const entry = agentStatusById.value[agentId] || null;
    const status = entry?.status || 'unknown';
    return {
      agentId,
      status,
      severity:
        status === 'online'
          ? 'success'
          : status === 'offline'
            ? 'danger'
            : 'secondary',
      lastSeenLabel: entry?.lastSeenLabel || '-',
    };
  });
});

const detectedAgentOptions = computed(() => {
  return Object.keys(agentStatusById.value)
    .sort((left, right) => left.localeCompare(right))
    .map((agentId) => {
      const status = agentStatusById.value[agentId]?.status || 'unknown';
      return {
        label: `${agentId} (${status})`,
        value: agentId,
      };
    });
});

const parseIsoTimestamp = (isoValue) => {
  const value = Date.parse(String(isoValue || ''));
  return Number.isFinite(value) ? value : null;
};

const toAgentState = (lastSeenRaw) => {
  const ts = parseIsoTimestamp(lastSeenRaw);
  if (ts === null) {
    return {
      status: 'unknown',
      lastSeenLabel: '-',
    };
  }

  const ageMs = Date.now() - ts;
  return {
    status: ageMs <= AGENT_ONLINE_THRESHOLD_MS ? 'online' : 'offline',
    lastSeenLabel: new Date(ts).toLocaleString(),
  };
};

const agentStatusLabelForDevice = (device) => {
  const agentId = String(device?.agentId || '').trim();
  if (!agentId) {
    return 'local';
  }

  return agentStatusById.value[agentId]?.status || 'unknown';
};

const applyAgentAvailabilityToDevices = () => {
  let changed = false;

  for (const device of devices.value) {
    const agentId = getDeviceAgentId(device);
    if (!agentId) {
      continue;
    }

    const agentStatus = agentStatusById.value[agentId]?.status || 'unknown';
    if (agentStatus === 'online') {
      continue;
    }

    const nextFeedback = `Agent ${agentId} is ${agentStatus}. TV status unavailable.`;
    if (device.status !== 'offline' || device.lastFeedback !== nextFeedback) {
      device.status = 'offline';
      device.lastFeedback = nextFeedback;
      device.lastChecked = new Date().toLocaleString();
      changed = true;
    }
  }

  if (changed) {
    saveDevices();
  }
};

const agentStatusSeverityForDevice = (device) => {
  const label = agentStatusLabelForDevice(device);
  if (label === 'online') {
    return 'success';
  }
  if (label === 'offline') {
    return 'danger';
  }
  return 'secondary';
};

const statusSeverity = (status) => {
  if (status === 'online') {
    return 'success';
  }
  if (status === 'offline') {
    return 'danger';
  }
  if (status === 'checking') {
    return 'warn';
  }
  return 'secondary';
};

const filteredDevices = computed(() => {
  const query = deviceSearch.value.trim().toLowerCase();
  return devices.value.filter((device) => {
    const statusMatches =
      statusFilter.value === 'all' || device.status === statusFilter.value;
    const siteMatches =
      siteFilter.value === 'all' ||
      String(device.site || '').trim() === siteFilter.value;
    const cityMatches =
      cityFilter.value === 'all' ||
      String(device.city || '').trim() === cityFilter.value;
    const textMatches =
      !query ||
      device.name.toLowerCase().includes(query) ||
      device.ip.toLowerCase().includes(query) ||
      String(device.displayId).includes(query) ||
      String(device.site || '')
        .toLowerCase()
        .includes(query) ||
      String(device.city || '')
        .toLowerCase()
        .includes(query) ||
      String(device.zone || '')
        .toLowerCase()
        .includes(query) ||
      String(device.area || '')
        .toLowerCase()
        .includes(query) ||
      String(device.description || '')
        .toLowerCase()
        .includes(query);

    return statusMatches && siteMatches && cityMatches && textMatches;
  });
});

const sortedFilteredDevices = computed(() => {
  const list = [...filteredDevices.value];
  const directionFactor = sortDirection.value === 'asc' ? 1 : -1;

  list.sort((left, right) => {
    if (sortBy.value === 'status') {
      const statusOrder = {
        online: 0,
        checking: 1,
        unknown: 2,
        offline: 3,
      };
      const leftValue = statusOrder[left.status] ?? 99;
      const rightValue = statusOrder[right.status] ?? 99;
      return (leftValue - rightValue) * directionFactor;
    }

    if (sortBy.value === 'lastChecked') {
      const leftTs = Date.parse(left.lastChecked || '') || 0;
      const rightTs = Date.parse(right.lastChecked || '') || 0;
      return (leftTs - rightTs) * directionFactor;
    }

    const leftName = String(left.name || '').toLowerCase();
    const rightName = String(right.name || '').toLowerCase();
    return leftName.localeCompare(rightName) * directionFactor;
  });

  return list;
});

const toggleSort = (column) => {
  if (sortBy.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
    return;
  }

  sortBy.value = column;
  sortDirection.value = 'asc';
};

const sortLabel = (column) => {
  if (sortBy.value !== column) {
    return '↕';
  }
  return sortDirection.value === 'asc' ? '↑' : '↓';
};

const parseApiResponse = async (response) => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return await response.json();
  }

  const text = await response.text();
  return {
    detail: `Non-JSON response from API (${response.status}). Check VITE_API_URL.`,
    raw: text.slice(0, 280),
  };
};

const pushLog = (line) => {
  const stamp = new Date().toLocaleTimeString();
  commandLogs.value = [`[${stamp}] ${line}`, ...commandLogs.value].slice(
    0,
    150,
  );
  saveCommandLogs();
};

const showToast = (severity, summary, detail, life = 2800) => {
  if (!IMPORTANT_TOAST_SEVERITIES.has(String(severity || '').toLowerCase())) {
    return;
  }
  toast.add({ severity, summary, detail, life });
};

const copyLastLog = async () => {
  const latestLog = commandLogs.value[0] || '';
  if (!latestLog) {
    showToast('warn', 'No Logs', 'There is no log entry to copy');
    return;
  }

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(latestLog);
    } else {
      const helperInput = document.createElement('textarea');
      helperInput.value = latestLog;
      helperInput.setAttribute('readonly', '');
      helperInput.style.position = 'fixed';
      helperInput.style.left = '-9999px';
      document.body.appendChild(helperInput);
      helperInput.select();
      document.execCommand('copy');
      document.body.removeChild(helperInput);
    }
    showToast('success', 'Copied', 'Latest log copied to clipboard', 1800);
  } catch (error) {
    const detail = formatClientError(error);
    pushLog(`Copy log error: ${detail}`);
    showToast('error', 'Copy Failed', detail);
  }
};

const clearLogs = () => {
  if (!commandLogs.value.length) {
    showToast('warn', 'No Logs', 'There are no log entries to clear');
    return;
  }

  const total = commandLogs.value.length;
  commandLogs.value = [];
  saveCommandLogs();
  appStatus.value = `Cleared ${total} log entries`;
  showToast('success', 'Logs Cleared', `${total} log entries removed`, 1800);
};

const saveLogsCsv = () => {
  if (!commandLogs.value.length) {
    showToast('warn', 'No Logs', 'There are no log entries to export');
    return;
  }

  const headers = ['index', 'time', 'message', 'raw'];
  const lines = [
    headers.join(','),
    ...commandLogs.value.map((entry, index) => {
      const raw = String(entry || '');
      const match = raw.match(/^\[(.*?)\]\s(.*)$/);
      const time = match?.[1] || '';
      const message = match?.[2] || raw;

      return [index + 1, time, message, raw]
        .map((value) => csvEscape(value))
        .join(',');
    }),
  ];

  const csvContent = lines.join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const stamp = new Date().toISOString().slice(0, 19).replaceAll(':', '-');
  link.href = url;
  link.download = `logs-${stamp}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  appStatus.value = `Exported ${commandLogs.value.length} logs to CSV`;
  pushLog(`Exported ${commandLogs.value.length} logs to CSV`);
  showToast(
    'success',
    'Logs Exported',
    `${commandLogs.value.length} logs saved`,
  );
};

const formatClientError = (error) => {
  const raw = error?.message || 'Unknown error';
  if (raw.toLowerCase().includes('failed to fetch')) {
    return 'API unreachable. Start backend on http://127.0.0.1:8000 and retry.';
  }
  return raw;
};

const formatConnectionToastDetail = (detail) => {
  const normalized = String(detail || '').toLowerCase();
  if (normalized.includes('no route to host')) {
    return 'No route to host';
  }
  return detail;
};

const parseMdcResultSummary = (resultValue) => {
  const text = String(resultValue ?? '').trim();
  if (!text) {
    return null;
  }

  const upper = text.toUpperCase();
  const hasNak = upper.includes('NAK') || upper.includes("'N'");
  const hasAck = upper.includes('ACK') || upper.includes("'A'");

  let status = null;
  if (hasNak) {
    status = 'NAK';
  } else if (hasAck) {
    status = 'ACK';
  }

  const errorCodeMatch = text.match(
    /(?:\bERR(?:OR)?\b\s*[:=]?\s*)(0X[0-9A-F]+|[0-9A-F]{2}|\d+)/i,
  );
  const errorCode = errorCodeMatch?.[1] || null;

  if (!status && !errorCode) {
    return null;
  }

  const details = [];
  if (status) {
    details.push(status);
  }
  if (errorCode) {
    details.push(`ERR=${errorCode}`);
  }

  return `MDC response ${details.join(' ')}`;
};

const saveDevices = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(devices.value));
};

const saveCommandLogs = () => {
  localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(commandLogs.value));
};

const loadCommandLogs = () => {
  try {
    const raw = localStorage.getItem(LOGS_STORAGE_KEY);
    if (!raw) {
      commandLogs.value = [];
      return;
    }

    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      commandLogs.value = parsed
        .map((entry) => String(entry || '').trim())
        .filter((entry) => entry.length > 0)
        .slice(0, 150);
      return;
    }
  } catch {}

  commandLogs.value = [];
};

const parseCsvArgs = (rawText) => {
  return rawText
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
};

const parseGenericArgValue = (rawValue) => {
  const text = String(rawValue ?? '').trim();
  if (!text.length) {
    return text;
  }

  if (/^-?\d+$/.test(text)) {
    return Number.parseInt(text, 10);
  }

  if (/^-?\d+\.\d+$/.test(text)) {
    return Number(text);
  }

  if (/^(true|false)$/i.test(text)) {
    return text.toLowerCase() === 'true';
  }

  return text;
};

const coerceMdcArgValue = (rawValue, fieldMeta) => {
  const text = String(rawValue ?? '').trim();
  if (!text.length) {
    return text;
  }

  if (!fieldMeta) {
    return parseGenericArgValue(text);
  }

  if (Array.isArray(fieldMeta.enum) && fieldMeta.enum.length) {
    return text;
  }

  if (fieldMeta.range) {
    const numeric = Number(text);
    if (!Number.isFinite(numeric)) {
      return text;
    }
    return Number.isInteger(fieldMeta.range.min) &&
      Number.isInteger(fieldMeta.range.max)
      ? Math.trunc(numeric)
      : numeric;
  }

  if (
    String(fieldMeta.type || '')
      .toLowerCase()
      .includes('bool')
  ) {
    if (/^(1|true|on)$/i.test(text)) {
      return true;
    }
    if (/^(0|false|off)$/i.test(text)) {
      return false;
    }
  }

  return parseGenericArgValue(text);
};

const formatMdcFieldValue = (value) => {
  if (Array.isArray(value)) {
    return value.map((item) => formatMdcFieldValue(item)).join(', ');
  }

  if (value === null || value === undefined) {
    return '';
  }

  if (typeof value === 'object') {
    return JSON.stringify(value);
  }

  return String(value);
};

const formatFieldLabel = (fieldName) => {
  return String(fieldName || '')
    .toLowerCase()
    .split('_')
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
};

const openCommandInfo = () => {
  if (!selectedMdcCommand.value) {
    showToast('warn', 'No Command Selected', 'Select an MDC command first');
    return;
  }

  isCommandInfoOpen.value = true;
};

const mdcFieldValues = ref({});

const mdcGetDefaultFieldCatalog = {
  holiday_get: {
    index: '0',
  },
};

const getMdcGetAutoValue = (commandName, field) => {
  const fieldName = String(field?.name || '');
  const commandDefaults = mdcGetDefaultFieldCatalog[commandName] || {};

  if (Object.hasOwn(commandDefaults, fieldName)) {
    return String(commandDefaults[fieldName]);
  }

  if (Array.isArray(field?.enum) && field.enum.length) {
    return String(field.enum[0]);
  }

  if (field?.range && Number.isFinite(field.range.min)) {
    return String(field.range.min);
  }

  return '';
};

const resetMdcFieldValues = () => {
  const nextValues = {};
  const isGetOperation = mdcOperation.value === 'get';
  const commandName = selectedMdcCommand.value;

  for (const field of selectedMdcFields.value) {
    nextValues[field.name] = isGetOperation
      ? getMdcGetAutoValue(commandName, field)
      : '';
  }
  mdcFieldValues.value = nextValues;
};

watch(selectedMdcCommand, () => {
  resetMdcFieldValues();
  mdcArgsText.value = '';
});

watch(mdcOperation, (nextOperation, previousOperation) => {
  if (nextOperation === 'get' || previousOperation === 'get') {
    resetMdcFieldValues();
  }

  if (nextOperation === 'get') {
    mdcArgsText.value = '';
  }
});

const autoMdcArgs = computed(() => {
  return selectedMdcFields.value
    .map((field) => String(mdcFieldValues.value[field.name] || '').trim())
    .filter((value) => value.length > 0);
});

const effectiveMdcArgs = computed(() => {
  const manualValues = parseCsvArgs(mdcArgsText.value);
  if (manualValues.length) {
    return manualValues;
  }
  return autoMdcArgs.value;
});

const effectiveTypedMdcArgs = computed(() => {
  const manualValues = parseCsvArgs(mdcArgsText.value);
  if (manualValues.length) {
    return manualValues.map((value, index) =>
      coerceMdcArgValue(value, selectedMdcFields.value[index]),
    );
  }

  return selectedMdcFields.value
    .map((field) => String(mdcFieldValues.value[field.name] || '').trim())
    .filter((value) => value.length > 0)
    .map((value, index) =>
      coerceMdcArgValue(value, selectedMdcFields.value[index]),
    );
});

const runInBatches = async (items, batchSize, worker) => {
  for (let index = 0; index < items.length; index += batchSize) {
    const batch = items.slice(index, index + batchSize);
    await Promise.allSettled(batch.map((item) => worker(item)));
  }
};

const REQUEST_TIMEOUT_MS = 10000;
const REMOTE_JOB_POLL_INTERVAL_MS = 1200;
const REMOTE_JOB_TIMEOUT_MS = 25000;

const normalizeTarget = (rawIp, rawPort) => {
  const fallbackPort = Number(rawPort) || 1515;
  const ipText = String(rawIp || '').trim();

  if (!ipText) {
    return { ip: '', port: fallbackPort };
  }

  const match = ipText.match(/^([^:]+):(\d{1,5})$/);
  if (!match) {
    return { ip: ipText, port: fallbackPort };
  }

  const parsedPort = Number(match[2]);
  if (parsedPort >= 1 && parsedPort <= 65535) {
    return { ip: match[1], port: parsedPort };
  }

  return { ip: match[1], port: fallbackPort };
};

const fetchWithTimeout = async (
  url,
  options = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
) => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(
        `Request timed out after ${Math.round(timeoutMs / 1000)}s`,
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
};

const remoteHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  if (cloudApiKey) {
    headers['x-api-key'] = cloudApiKey;
  }
  return headers;
};

const fetchRemoteAgents = async ({ silent = false } = {}) => {
  if (!API_BASE) {
    return false;
  }

  try {
    const response = await fetchWithTimeout(`${API_BASE}/api/remote/agents`, {
      headers: remoteHeaders(),
    });
    const data = await parseApiResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to load remote agents');
    }

    const nextState = {};
    for (const agent of data.agents || []) {
      const agentId = String(agent?.agent_id || '').trim();
      if (!agentId) {
        continue;
      }

      nextState[agentId] = toAgentState(agent.last_seen);
    }

    agentStatusById.value = nextState;
    applyAgentAvailabilityToDevices();
    agentsLastUpdatedAt.value = new Date().toLocaleString();

    return true;
  } catch (error) {
    if (!silent) {
      const detail = formatClientError(error);
      pushLog(`Agent status error: ${detail}`);
      showToast('warn', 'Agent Status', detail);
    }

    return false;
  }
};

const refreshAgentStatusManual = async () => {
  if (isAgentRefreshBusy.value) {
    return;
  }

  isAgentRefreshBusy.value = true;
  appStatus.value = 'Refreshing agent status...';

  try {
    const ok = await fetchRemoteAgents();
    if (!ok) {
      appStatus.value = 'Agent status refresh failed';
      return;
    }

    const states = Object.values(agentStatusById.value || {});
    const total = states.length;
    const online = states.filter((entry) => entry?.status === 'online').length;
    const offline = states.filter(
      (entry) => entry?.status === 'offline',
    ).length;
    appStatus.value = `Agent status updated: ${online} online, ${offline} offline (${total} total)`;
    toast.add({
      severity: 'success',
      summary: 'Agent Status Updated',
      detail: `${online} online, ${offline} offline`,
      life: 2200,
    });
  } finally {
    isAgentRefreshBusy.value = false;
  }
};

const autoDetectAddAgentId = () => {
  const statuses = agentStatusById.value || {};
  const allAgentIds = Object.keys(statuses).sort((left, right) =>
    left.localeCompare(right),
  );

  if (!allAgentIds.length) {
    showToast('warn', 'Agent Detect', 'No agents detected from backend yet');
    return;
  }

  const onlineAgentIds = allAgentIds.filter(
    (agentId) => statuses[agentId]?.status === 'online',
  );

  if (onlineAgentIds.length === 1) {
    addAgentId.value = onlineAgentIds[0];
    appStatus.value = `Auto detected Agent ID: ${onlineAgentIds[0]}`;
    return;
  }

  if (onlineAgentIds.length > 1) {
    appStatus.value = `Multiple online agents found (${onlineAgentIds.length}). Select one from Agent ID list.`;
    showToast(
      'warn',
      'Agent Detect',
      `Multiple online agents found (${onlineAgentIds.length})`,
    );
    return;
  }

  if (allAgentIds.length === 1) {
    addAgentId.value = allAgentIds[0];
    appStatus.value = `Auto detected Agent ID: ${allAgentIds[0]}`;
    return;
  }

  appStatus.value = `No online agents detected. Select from ${allAgentIds.length} known Agent IDs.`;
};

const getDeviceAgentId = (device) => String(device?.agentId || '').trim();

const enqueueRemoteJob = async (agentId, kind, payload) => {
  const response = await fetchWithTimeout(`${API_BASE}/api/remote/jobs`, {
    method: 'POST',
    headers: remoteHeaders(),
    body: JSON.stringify({
      agent_id: agentId,
      kind,
      payload,
    }),
  });
  const data = await parseApiResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || 'Failed to enqueue remote job');
  }
  return data;
};

const pollRemoteJob = async (jobId, timeoutMs = REMOTE_JOB_TIMEOUT_MS) => {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const response = await fetchWithTimeout(
      `${API_BASE}/api/remote/jobs/${encodeURIComponent(jobId)}`,
      {
        headers: remoteHeaders(),
      },
    );
    const data = await parseApiResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to read remote job status');
    }

    if (data.status === 'completed') {
      return data;
    }

    if (data.status === 'failed') {
      throw new Error(data.error || 'Remote agent execution failed');
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, REMOTE_JOB_POLL_INTERVAL_MS);
    });
  }

  throw new Error(
    `Remote job timeout after ${Math.round(timeoutMs / 1000)}s. Agent may be offline.`,
  );
};

const executeRemoteJob = async (
  device,
  kind,
  payload,
  timeoutMs = REMOTE_JOB_TIMEOUT_MS,
) => {
  const agentId = getDeviceAgentId(device);
  if (!agentId) {
    throw new Error('Missing Agent ID on device');
  }

  const queued = await enqueueRemoteJob(agentId, kind, payload);
  const completed = await pollRemoteJob(queued.job_id, timeoutMs);
  if (!completed?.result || typeof completed.result !== 'object') {
    throw new Error('Remote job completed without result payload');
  }
  return completed.result.data;
};

const normalizeProtocol = (protocol) => {
  const normalized = String(protocol || 'AUTO')
    .trim()
    .toUpperCase();
  return normalized === PROTOCOL_SIGNAGE_MDC || normalized === 'MDC'
    ? PROTOCOL_SIGNAGE_MDC
    : 'AUTO';
};

const protocolLabel = (protocol) =>
  normalizeProtocol(protocol) === PROTOCOL_SIGNAGE_MDC ? 'MDC' : 'AUTO';

const normalizeDevice = (device) => {
  const target = normalizeTarget(device?.ip, device?.port);
  const protocol = normalizeProtocol(device?.protocol);
  const port =
    protocol === PROTOCOL_SIGNAGE_MDC &&
    (target.port === 8001 || target.port === 8002)
      ? 1515
      : target.port;

  return {
    id: String(device?.id || Date.now() + Math.random()),
    name: String(device?.name || 'Unnamed Screen'),
    ip: target.ip,
    port,
    displayId: Number(device?.displayId) || 0,
    protocol,
    agentId: String(device?.agentId || ''),
    site: String(device?.site || ''),
    city: String(device?.city || ''),
    zone: String(device?.zone || ''),
    area: String(device?.area || ''),
    description: String(device?.description || ''),
    status: String(device?.status || 'unknown'),
    lastFeedback: String(device?.lastFeedback || 'No checks yet'),
    lastChecked: String(device?.lastChecked || '-'),
  };
};

const csvEscape = (value) => {
  const raw = String(value ?? '');
  if (raw.includes(',') || raw.includes('"') || raw.includes('\n')) {
    return `"${raw.replaceAll('"', '""')}"`;
  }
  return raw;
};

const parseCsvLine = (line) => {
  const values = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];

    if (char === '"') {
      const isEscapedQuote = inQuotes && line[index + 1] === '"';
      if (isEscapedQuote) {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      values.push(current);
      current = '';
      continue;
    }

    current += char;
  }

  values.push(current);
  return values.map((value) => value.trim());
};

const exportDevicesCsv = () => {
  if (!devices.value.length) {
    appStatus.value = 'No devices to export';
    showToast('warn', 'Export Skipped', 'There are no devices to export');
    return;
  }

  const headers = [
    'name',
    'ip',
    'port',
    'displayId',
    'protocol',
    'agentId',
    'site',
    'city',
    'zone',
    'area',
    'description',
  ];

  const lines = [
    headers.join(','),
    ...devices.value.map((device) =>
      [
        device.name,
        device.ip,
        device.port,
        device.displayId,
        device.protocol,
        device.agentId,
        device.site,
        device.city,
        device.zone,
        device.area,
        device.description,
      ]
        .map((value) => csvEscape(value))
        .join(','),
    ),
  ];

  const csvContent = lines.join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const stamp = new Date().toISOString().slice(0, 19).replaceAll(':', '-');
  link.href = url;
  link.download = `screens-${stamp}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  appStatus.value = `Exported ${devices.value.length} screens to CSV`;
  pushLog(`Exported ${devices.value.length} screens`);
  showToast(
    'success',
    'CSV Exported',
    `${devices.value.length} screens exported`,
  );
};

const openImportDialog = () => {
  if (!csvFileInput.value) {
    showToast('error', 'Import Unavailable', 'CSV file input is not ready yet');
    return;
  }

  csvFileInput.value.click();
};

const importDevicesCsv = async (event) => {
  const file = event.target?.files?.[0];
  if (!file) {
    return;
  }

  try {
    const text = await file.text();
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (lines.length < 2) {
      appStatus.value = 'CSV is empty or missing rows';
      showToast('warn', 'Invalid CSV', 'CSV is empty or missing data rows');
      return;
    }

    const headers = parseCsvLine(lines[0]).map((header) =>
      header.trim().toLowerCase(),
    );
    const imported = [];

    for (const line of lines.slice(1)) {
      const values = parseCsvLine(line);
      const row = Object.fromEntries(
        headers.map((header, index) => [header, values[index] || '']),
      );

      if (!row.ip) {
        continue;
      }

      imported.push(
        normalizeDevice({
          id: String(Date.now() + Math.random()),
          name: row.name || 'Imported Screen',
          ip: row.ip,
          port: Number(row.port) || 1515,
          displayId: Number(row.displayid) || 0,
          protocol: row.protocol || 'AUTO',
          agentId: row.agentid || '',
          site: row.site || '',
          city: row.city || '',
          zone: row.zone || '',
          area: row.area || '',
          description: row.description || '',
          status: 'unknown',
          lastFeedback: 'Imported from CSV',
          lastChecked: '-',
        }),
      );
    }

    if (!imported.length) {
      appStatus.value = 'No valid rows found in CSV';
      showToast('warn', 'Import Skipped', 'No valid device rows found in CSV');
      return;
    }

    devices.value = [...devices.value, ...imported];
    if (!selectedDeviceId.value && devices.value.length > 0) {
      selectedDeviceId.value = devices.value[0].id;
    }
    saveDevices();
    appStatus.value = `Imported ${imported.length} screens from CSV`;
    pushLog(`Imported ${imported.length} screens from CSV`);
    showToast('success', 'CSV Imported', `${imported.length} screens imported`);
  } catch (error) {
    const detail = formatClientError(error);
    appStatus.value = `CSV import failed: ${detail}`;
    pushLog(`CSV import failed: ${detail}`);
    showToast('error', 'Import Failed', detail);
  } finally {
    if (event.target) {
      event.target.value = '';
    }
  }
};

const testTargetText = (device) => {
  return `${device.ip}:${device.port} (${protocolLabel(device.protocol)}, ID ${device.displayId})`;
};

const autoProbe = async (ip, displayId) => {
  const target = normalizeTarget(ip, null);
  const params = new URLSearchParams({
    display_id: String(displayId ?? 0),
    timeout: '1.5',
  });

  const response = await fetchWithTimeout(
    `${API_BASE}/api/probe/${encodeURIComponent(target.ip)}?${params.toString()}`,
  );
  const data = await parseApiResponse(response);

  if (!response.ok) {
    throw new Error(
      data.detail || `Auto probe request failed (${response.status})`,
    );
  }

  return data;
};

const toPayload = (device) => ({
  ip: device.ip.trim(),
  port: Number(device.port),
  display_id: Number(device.displayId),
  protocol: device.protocol,
});

const loadDevices = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const normalizedDevices = parsed.map((device) =>
          normalizeDevice(device),
        );
        devices.value = normalizedDevices;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizedDevices));
        selectedDeviceId.value = devices.value[0]?.id || null;
        return;
      }
    }
  } catch {}

  devices.value = [];
  selectedDeviceId.value = null;
};

const fetchMdcCommands = async () => {
  try {
    const response = await fetchWithTimeout(`${API_BASE}/api/mdc/commands`);
    const data = await parseApiResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to load MDC commands');
    }
    mdcCommands.value = data.commands || [];
    if (mdcCommands.value.length > 0) {
      selectedMdcCommand.value = mdcCommands.value[0].name;
    }
    pushLog(`Loaded ${mdcCommands.value.length} MDC commands`);
  } catch (error) {
    const detail = formatClientError(error);
    pushLog(`MDC catalog error: ${detail}`);
    showToast('warn', 'MDC Commands', detail);
  }
};

const checkDevice = async (device, options = {}) => {
  const isBulk = Boolean(options.isBulk);
  const target = normalizeTarget(device.ip, device.port);
  device.ip = target.ip;
  device.port = target.port;

  try {
    device.status = 'checking';
    device.lastFeedback = `Testing ${testTargetText(device)}...`;
    if (!isBulk) {
      appStatus.value = `Testing ${device.name} on ${testTargetText(device)}...`;
      pushLog(`Testing ${device.name} on ${testTargetText(device)}`);
      saveDevices();
    }

    const agentId = getDeviceAgentId(device);

    let data;
    if (agentId) {
      const agentStatus = agentStatusById.value[agentId]?.status || 'unknown';
      if (agentStatus !== 'online') {
        throw new Error(
          `Agent ${agentId} is ${agentStatus}. TV check requires online agent.`,
        );
      }

      data = await executeRemoteJob(device, 'test', {
        ...toPayload(device),
      });
    } else {
      const params = new URLSearchParams({
        protocol: device.protocol,
        display_id: String(device.displayId),
        port: String(device.port),
      });
      const response = await fetchWithTimeout(
        `${API_BASE}/api/test/${encodeURIComponent(device.ip)}?${params.toString()}`,
      );
      data = await parseApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || 'Offline');
      }
    }

    device.status = 'online';
    device.lastFeedback = `Reachable via ${protocolLabel(data.protocol)} on port ${data.port}`;
    device.lastChecked = new Date().toLocaleString();
    if (!isBulk) {
      appStatus.value = `${device.name}: online (${protocolLabel(data.protocol)})`;
      pushLog(`Test success ${device.name}: ${device.lastFeedback}`);
      showToast(
        'success',
        'Connection OK',
        `${device.name} is online (${protocolLabel(data.protocol)})`,
      );
    }
  } catch (error) {
    device.status = 'offline';
    device.lastFeedback = error.message;
    device.lastChecked = new Date().toLocaleString();
    if (!isBulk) {
      appStatus.value = `${device.name}: offline`;
      pushLog(`Test failed ${device.name}: ${error.message}`);
      const toastDetail = formatConnectionToastDetail(error.message);
      showToast('error', 'Connection Failed', toastDetail);
    }
  }

  if (!isBulk) {
    saveDevices();
  }
};

const refreshAllDevices = async () => {
  if (!API_BASE) {
    appStatus.value = 'VITE_API_URL is not set';
    showToast(
      'error',
      'API URL Missing',
      'Set VITE_API_URL and reload the app',
    );
    return;
  }

  if (!devices.value.length) {
    appStatus.value = 'No devices to refresh';
    showToast(
      'warn',
      'Refresh Skipped',
      'Add or import at least one device first',
    );
    return;
  }

  appStatus.value = `Refreshing ${devices.value.length} device statuses...`;
  for (const device of devices.value) {
    device.status = 'checking';
    device.lastFeedback = 'Queued for refresh...';
  }
  saveDevices();

  await runInBatches(
    devices.value,
    BULK_REFRESH_CONCURRENCY,
    async (device) => {
      await checkDevice(device, { isBulk: true });
    },
  );

  saveDevices();
  const onlineCount = devices.value.filter(
    (device) => device.status === 'online',
  ).length;
  const offlineCount = devices.value.filter(
    (device) => device.status === 'offline',
  ).length;
  appStatus.value = `Dashboard updated: ${onlineCount} online, ${offlineCount} offline`;
  pushLog(
    `Refresh all completed: ${onlineCount} online, ${offlineCount} offline`,
  );
  showToast(
    'info',
    'Refresh Completed',
    `${onlineCount} online, ${offlineCount} offline`,
  );
};

const addDevice = () => {
  const name = addName.value.trim();
  const agentId = addAgentId.value.trim();
  const target = normalizeTarget(addIp.value, addPort.value);

  if (!name) {
    appStatus.value = 'Device Name is required';
    showToast('warn', 'Missing Field', 'Device Name is required');
    return;
  }

  if (!target.ip) {
    appStatus.value = 'Device IP is required';
    showToast('warn', 'Missing Field', 'Device IP is required');
    return;
  }

  if (!agentId) {
    appStatus.value = 'Agent ID is required';
    showToast('warn', 'Missing Field', 'Agent ID is required');
    return;
  }

  const item = {
    id: String(Date.now() + Math.random()),
    name,
    ip: target.ip,
    port: target.port,
    displayId: Number(addDisplayId.value) || 0,
    protocol: addProtocol.value,
    agentId,
    site: addSite.value.trim(),
    city: addCity.value.trim(),
    zone: addZone.value.trim(),
    area: addArea.value.trim(),
    description: addDescription.value.trim(),
    status: 'unknown',
    lastFeedback: 'No checks yet',
    lastChecked: '-',
  };

  devices.value.push(item);
  saveDevices();
  appStatus.value = `Added ${item.name}`;
  showToast('success', 'Device Added', `${item.name} added to dashboard`);

  addName.value = '';
  addIp.value = '';
  addPort.value = '';
  addDisplayId.value = '';
  addProtocol.value = 'AUTO';
  addAgentId.value = '';
  addSite.value = '';
  addCity.value = '';
  addZone.value = '';
  addArea.value = '';
  addDescription.value = '';
};

const clearFilters = () => {
  deviceSearch.value = '';
  siteFilter.value = 'all';
  cityFilter.value = 'all';
  statusFilter.value = 'all';
  appStatus.value = 'Filters cleared';
  showToast('info', 'Filters Cleared', 'All filters were reset');
};

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

const autoProbeAddDraft = async () => {
  const target = normalizeTarget(addIp.value, addPort.value);
  const agentId = addAgentId.value.trim();

  if (!target.ip) {
    appStatus.value = 'Enter IP before auto probe';
    showToast('warn', 'Missing IP', 'Enter device IP before Detect Connection');
    return;
  }

  try {
    appStatus.value = `Probing ${target.ip}...`;
    const displayId = Number(addDisplayId.value) || 0;
    const data = agentId
      ? await executeRemoteJob(
          { agentId },
          'probe',
          {
            ip: target.ip,
            display_id: displayId,
            timeout: 1.5,
          },
          30000,
        )
      : await autoProbe(target.ip, displayId);

    if (!data.found) {
      appStatus.value = 'No known Samsung control port found';
      showToast(
        'warn',
        'No Port Found',
        'No known Samsung control port was detected',
      );
      return;
    }

    addPort.value = String(data.port);
    addProtocol.value = normalizeProtocol(data.protocol);
    const verificationText = data.verified ? 'verified' : 'inferred';
    appStatus.value = `Detected ${protocolLabel(data.protocol)} on port ${data.port} (${verificationText})`;
    const severity = data.verified ? 'success' : 'info';
    showToast(
      severity,
      'Connection Detected',
      `${protocolLabel(data.protocol)} on port ${data.port} (${verificationText})`,
    );
  } catch (error) {
    const detail = formatClientError(error);
    appStatus.value = `Auto probe failed: ${detail}`;
    pushLog(`Auto probe failed for ${addIp.value}: ${detail}`);
    showToast('error', 'Detect Failed', detail);
  }
};

const deleteDevice = (id) => {
  const deleted = devices.value.find((device) => device.id === id);
  devices.value = devices.value.filter((device) => device.id !== id);
  selectedDeviceRows.value = selectedDeviceRows.value.filter(
    (device) => device.id !== id,
  );
  if (selectedDeviceId.value === id) {
    selectedDeviceId.value = devices.value[0]?.id || null;
    currentView.value = devices.value.length ? 'device' : 'dashboard';
  }
  saveDevices();
  if (deleted) {
    appStatus.value = `Deleted ${deleted.name}`;
    showToast('info', 'Device Deleted', `${deleted.name} removed`);
  }
};

const requestDeleteSelectedDevices = () => {
  if (!selectedDeviceRows.value.length) {
    showToast('warn', 'No Selection', 'Select at least one screen to delete');
    return;
  }

  const count = selectedDeviceRows.value.length;
  confirm.require({
    header: 'Delete selected screens',
    message: `Are you sure you want to delete ${count} screen${count > 1 ? 's' : ''}?`,
    acceptLabel: 'Yes',
    rejectLabel: 'No',
    acceptClass: 'p-button-danger',
    rejectClass: 'p-button-secondary p-button-outlined',
    accept: () => {
      const selectedIds = new Set(
        selectedDeviceRows.value.map((device) => device.id),
      );
      const deletingSelected = selectedIds.has(selectedDeviceId.value);

      devices.value = devices.value.filter(
        (device) => !selectedIds.has(device.id),
      );
      selectedDeviceRows.value = [];

      if (deletingSelected) {
        selectedDeviceId.value = devices.value[0]?.id || null;
        currentView.value = devices.value.length ? 'device' : 'dashboard';
      }

      saveDevices();
      appStatus.value = `Deleted ${count} screen${count > 1 ? 's' : ''}`;
      showToast(
        'info',
        'Screens Deleted',
        `${count} screen${count > 1 ? 's' : ''} removed`,
      );
    },
  });
};

const requestDeleteDevice = (device) => {
  if (!device) {
    return;
  }

  confirm.require({
    header: 'Delete device',
    message: `Are you sure you want to delete "${device.name}"?`,
    acceptLabel: 'Yes',
    rejectLabel: 'No',
    acceptClass: 'p-button-danger',
    rejectClass: 'p-button-secondary p-button-outlined',
    accept: () => {
      deleteDevice(device.id);
    },
  });
};

const openDevice = (device) => {
  selectedDeviceId.value = device.id;
  currentView.value = 'device';
  appStatus.value = `Opened ${device.name}`;
  showToast('info', 'Device Opened', device.name, 1800);
};

const openDeviceControl = () => {
  currentView.value = 'device';

  if (!selectedDevice.value) {
    appStatus.value =
      'Device Control opened. Add/import a device, then select one.';
  }
};

const runSelectedDeviceTest = async () => {
  if (!selectedDevice.value || isDeviceTestBusy.value) {
    return;
  }

  isDeviceTestBusy.value = true;
  try {
    await checkDevice(selectedDevice.value);
  } finally {
    isDeviceTestBusy.value = false;
  }
};

const saveSelectedDevice = () => {
  if (!selectedDevice.value) {
    showToast('warn', 'No Device Selected', 'Select a device first');
    return;
  }

  if (!selectedDevice.value.ip?.trim()) {
    appStatus.value = 'Device IP is required';
    showToast('warn', 'Missing Field', 'Device IP is required');
    return;
  }

  saveDevices();
  appStatus.value = 'Device details saved';
  toast.add({
    severity: 'success',
    summary: 'Device Saved',
    detail: `${selectedDevice.value.name} updated`,
    life: 2800,
  });
};

const runPower = async (command) => {
  if (isPowerBusy.value) {
    return;
  }

  if (!selectedDevice.value) {
    showToast('warn', 'No Device Selected', 'Select a device first');
    return;
  }

  isPowerBusy.value = true;
  try {
    appStatus.value = `Sending ${command.toUpperCase()}...`;
    const agentId = getDeviceAgentId(selectedDevice.value);
    let data;
    if (agentId) {
      data = await executeRemoteJob(selectedDevice.value, 'tv', {
        ip: selectedDevice.value.ip,
        command,
        display_id: Number(selectedDevice.value.displayId),
        port: Number(selectedDevice.value.port),
        protocol: selectedDevice.value.protocol,
      });
    } else {
      const params = new URLSearchParams({
        protocol: selectedDevice.value.protocol,
        display_id: String(selectedDevice.value.displayId),
        port: String(selectedDevice.value.port),
      });
      const response = await fetch(
        `${API_BASE}/api/tv/${encodeURIComponent(selectedDevice.value.ip)}/${command}?${params.toString()}`,
      );
      data = await parseApiResponse(response);
      if (!response.ok) {
        throw new Error(data.detail || 'Power command failed');
      }
    }
    appStatus.value = `Power ${command.toUpperCase()} sent`;
    pushLog(
      `Power ${command.toUpperCase()} on ${selectedDevice.value.ip} via ${data.protocol}`,
    );
    showToast(
      'success',
      'Power Command Sent',
      `${selectedDevice.value.name}: ${command.toUpperCase()}`,
    );
  } catch (error) {
    const detail = formatClientError(error);
    appStatus.value = detail;
    pushLog(`Power error: ${detail}`);
    showToast('error', 'Power Command Failed', detail);
  } finally {
    isPowerBusy.value = false;
  }
};

const requestPowerAction = (command) => {
  if (command !== 'off') {
    runPower(command);
    return;
  }

  confirm.require({
    header: 'Power OFF',
    message: `Are you sure you want to power OFF "${selectedDevice.value?.name || 'this device'}"?`,
    acceptLabel: 'Yes',
    rejectLabel: 'No',
    acceptClass: 'p-button-danger',
    rejectClass: 'p-button-secondary p-button-outlined',
    accept: () => {
      runPower('off');
    },
  });
};

const isMdcCommandAvailable = (commandName) => {
  return mdcCommands.value.some((item) => item.name === commandName);
};

const clamp = (value, min, max) => {
  return Math.min(max, Math.max(min, value));
};

const effectiveProtocolForDevice = (device) => {
  const protocol = String(device?.protocol || 'AUTO')
    .trim()
    .toUpperCase();
  if (protocol === 'AUTO') {
    return PROTOCOL_SIGNAGE_MDC;
  }
  return protocol;
};

const executeMdcCommand = async (command, operation, args = []) => {
  if (isMdcBusy.value) {
    pushLog('MDC command skipped: another MDC command is already running');
    return null;
  }

  if (!selectedDevice.value) {
    pushLog('MDC command blocked: no device selected');
    showToast('warn', 'No Device Selected', 'Select a device first');
    return null;
  }

  if (!command) {
    pushLog('MDC command blocked: missing command name');
    showToast('warn', 'Missing Field', 'Select an MDC command first');
    return null;
  }

  isMdcBusy.value = true;
  try {
    appStatus.value = `Running ${command}...`;
    const payload = {
      ...toPayload(selectedDevice.value),
      command,
      args,
      operation,
    };
    const argsText = Array.isArray(args)
      ? args.map((value) => String(value)).join(', ')
      : '';
    pushLog(
      `MDC request ${command} (${operation}) args=[${argsText || '-'}] on ${selectedDevice.value.ip}:${selectedDevice.value.port} id=${selectedDevice.value.displayId}`,
    );

    const submitMdcExecute = async (requestPayload) => {
      const agentId = getDeviceAgentId(selectedDevice.value);

      if (agentId) {
        const remoteData = await executeRemoteJob(
          selectedDevice.value,
          'mdc_execute',
          requestPayload,
        );
        if (!remoteData || typeof remoteData !== 'object') {
          throw new Error('MDC command failed (invalid remote response)');
        }
        return remoteData;
      }

      const response = await fetch(`${API_BASE}/api/mdc/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
      });
      const data = await parseApiResponse(response);
      if (!response.ok) {
        throw new Error(data.detail || 'MDC command failed');
      }
      return data;
    };

    let data;
    try {
      data = await submitMdcExecute(payload);
    } catch (error) {
      const rawDetail = String(error?.message || '');
      const protocolRejected = rawDetail
        .toLowerCase()
        .includes('requires signage_mdc protocol');

      if (!protocolRejected) {
        throw error;
      }

      const fallbackPort = Number(defaultPort) || 1515;
      const fallbackPayload = {
        ...payload,
        protocol: PROTOCOL_SIGNAGE_MDC,
        port: fallbackPort,
      };

      pushLog(
        `MDC fallback: retry ${command} on MDC:${fallbackPort} (device protocol is ${protocolLabel(selectedDevice.value.protocol)})`,
      );
      showToast(
        'info',
        'MDC Retry',
        `Retrying ${command} on MDC:${fallbackPort}`,
        2400,
      );

      data = await submitMdcExecute(fallbackPayload);
    }

    appStatus.value = `${data.command} done`;
    const formattedArgs = Array.isArray(data.args)
      ? data.args.map((value) => String(value)).join(', ')
      : '';
    pushLog(
      `MDC ${data.command} (${data.operation}) args=[${formattedArgs || '-'}] => ${data.result}`,
    );
    const mdcResponseSummary = parseMdcResultSummary(data.result);
    if (mdcResponseSummary) {
      pushLog(mdcResponseSummary);
    }
    pushLog(
      `MDC target: display_ip=${data.tv} display_id=${data.display_id} port=${data.port}`,
    );

    if (
      data.operation === 'get' &&
      Array.isArray(data.result_values) &&
      selectedMdcCommand.value === data.command
    ) {
      const nextFieldValues = { ...mdcFieldValues.value };
      selectedMdcFields.value.forEach((field, index) => {
        if (index >= data.result_values.length) {
          return;
        }
        nextFieldValues[field.name] = formatMdcFieldValue(
          data.result_values[index],
        );
      });
      mdcFieldValues.value = nextFieldValues;
    }

    toast.add({
      severity: 'success',
      summary: 'MCD COMAND SUCCEDET',
      detail: `${data.command} (${data.operation}) executed`,
      life: 2800,
    });
    return data;
  } catch (error) {
    const detail = formatClientError(error);
    appStatus.value = detail;
    pushLog(`MDC error: ${detail}`);
    showToast('error', 'MDC Comand Failds', 'Check logs for details');
    return null;
  } finally {
    isMdcBusy.value = false;
  }
};

const runMdcCommand = async () => {
  await executeMdcCommand(
    selectedMdcCommand.value,
    mdcOperation.value,
    effectiveTypedMdcArgs.value,
  );
};

const runMdcQuickAction = async (action) => {
  if (!isMdcCommandAvailable(action.command)) {
    showToast(
      'warn',
      'Command Unavailable',
      `${action.command} is not available on this backend`,
    );
    return;
  }

  selectedMdcCommand.value = action.command;
  mdcOperation.value = action.operation;
  mdcArgsText.value = (action.args || []).join(',');
  await executeMdcCommand(action.command, action.operation, action.args || []);
};

const runMuteQuickAction = async (isOn) => {
  const targetState = isOn ? 'ON' : 'OFF';

  if (isMdcCommandAvailable('mute')) {
    await runMdcQuickAction({
      command: 'mute',
      operation: 'set',
      args: [targetState],
    });
    return;
  }

  if (isMdcCommandAvailable('screen_mute')) {
    await runMdcQuickAction({
      command: 'screen_mute',
      operation: 'set',
      args: [targetState],
    });
    return;
  }

  showToast(
    'warn',
    'Command Unavailable',
    'Neither mute nor screen_mute is available on this backend',
  );
};

const setVolumeFromSlider = async () => {
  if (!selectedDevice.value) {
    showToast('warn', 'No Device Selected', 'Select a device first');
    return;
  }

  const effectiveProtocol = effectiveProtocolForDevice(selectedDevice.value);
  if (effectiveProtocol !== PROTOCOL_SIGNAGE_MDC) {
    showToast(
      'warn',
      'MDC Only',
      'Set Volume works only with MDC (port 1515).',
    );
    return;
  }

  if (!isMdcCommandAvailable('volume')) {
    showToast(
      'warn',
      'Command Unavailable',
      'volume is not available on this backend',
    );
    return;
  }

  const value = clamp(Number(volumeLevel.value) || 0, 0, 100);
  volumeLevel.value = value;
  selectedMdcCommand.value = 'volume';
  mdcOperation.value = 'set';
  mdcArgsText.value = String(value);
  await executeMdcCommand('volume', 'set', [value]);
};

const setBrightnessFromSlider = async () => {
  if (!selectedDevice.value) {
    showToast('warn', 'No Device Selected', 'Select a device first');
    return;
  }

  const effectiveProtocol = effectiveProtocolForDevice(selectedDevice.value);
  if (effectiveProtocol !== PROTOCOL_SIGNAGE_MDC) {
    showToast(
      'warn',
      'MDC Only',
      'Set Brightness works only with MDC (port 1515).',
    );
    return;
  }

  if (!isMdcCommandAvailable('brightness')) {
    showToast(
      'warn',
      'Command Unavailable',
      'brightness is not available on this backend',
    );
    return;
  }

  const value = clamp(Number(brightnessLevel.value) || 0, 0, 100);
  brightnessLevel.value = value;
  selectedMdcCommand.value = 'brightness';
  mdcOperation.value = 'set';
  mdcArgsText.value = String(value);
  await executeMdcCommand('brightness', 'set', [value]);
};

onMounted(async () => {
  loadCommandLogs();

  if (!API_BASE) {
    appStatus.value = 'VITE_API_URL is not set';
    showToast(
      'error',
      'API URL Missing',
      'Set VITE_API_URL and reload the app',
    );
    return;
  }

  loadDevices();
  await fetchMdcCommands();
  await fetchRemoteAgents({ silent: true });
  await refreshAllDevices();

  agentStatusRefreshInterval = window.setInterval(() => {
    fetchRemoteAgents({ silent: true });
  }, AGENT_STATUS_REFRESH_INTERVAL_MS);
});

onUnmounted(() => {
  if (agentStatusRefreshInterval) {
    window.clearInterval(agentStatusRefreshInterval);
    agentStatusRefreshInterval = null;
  }
});
</script>

<template>
  <main class="layout">
    <Toast position="top-right" />
    <ConfirmDialog />
    <aside class="sidebar">
      <div class="brand-logo" aria-label="Logo">
        <img
          v-if="showBrandLogo"
          :src="BRAND_LOGO_URL"
          alt="Samsung Display Hub logo"
          class="brand-logo-image"
          @error="showBrandLogo = false"
        />
        <i v-else class="pi pi-desktop"></i>
        <span>Samsung Display Hub</span>
      </div>
      <Button
        label="Devices"
        icon="pi pi-th-large"
        class="nav-button"
        :class="{ active: currentView === 'dashboard' }"
        text
        @click="currentView = 'dashboard'"
      />
      <Button
        label="Device Control"
        icon="pi pi-sliders-h"
        class="nav-button"
        :class="{ active: currentView === 'device' }"
        text
        @click="openDeviceControl"
      />
      <Button
        label="Explore Agents"
        icon="pi pi-sitemap"
        class="nav-button"
        :class="{ active: currentView === 'agents' }"
        text
        @click="currentView = 'agents'"
      />
    </aside>

    <section class="content">
      <Toolbar v-if="currentView === 'dashboard'" class="top-menu">
        <template #start>
          <div class="top-menu-title">{{ currentViewTitle }}</div>
        </template>
        <template #end>
          <div class="top-menu-actions">
            <input
              ref="csvFileInput"
              type="file"
              accept=".csv,text/csv"
              class="hidden-file-input"
              @change="importDevicesCsv"
            />
            <Button
              label="Add New Device"
              icon="pi pi-plus"
              @click="
                currentView === 'dashboard'
                  ? addDevice()
                  : (currentView = 'dashboard')
              "
            />
            <Button
              label="Import CSV"
              icon="pi pi-upload"
              severity="secondary"
              outlined
              @click="openImportDialog"
            />
            <Button
              label="Export CSV"
              icon="pi pi-download"
              severity="secondary"
              outlined
              @click="exportDevicesCsv"
            />
          </div>
        </template>
      </Toolbar>

      <section v-if="currentView === 'dashboard'" class="panel">
        <Card>
          <template #title>Add Device</template>
          <template #content>
            <div class="form-grid">
              <div class="field-stack">
                <label class="field-label">Device Name</label>
                <InputText v-model="addName" placeholder="Device name" />
              </div>
              <div class="field-stack">
                <label class="field-label">Site</label>
                <InputText v-model="addSite" placeholder="Site" />
              </div>
              <div class="field-stack">
                <label class="field-label">City</label>
                <InputText v-model="addCity" placeholder="City" />
              </div>
              <div class="field-stack">
                <label class="field-label">Zone</label>
                <InputText v-model="addZone" placeholder="Zone" />
              </div>
              <div class="field-stack">
                <label class="field-label">Area</label>
                <InputText v-model="addArea" placeholder="Area" />
              </div>
              <div class="field-stack">
                <label class="field-label">Description</label>
                <InputText v-model="addDescription" placeholder="Description" />
              </div>
              <div class="field-stack">
                <label class="field-label">IP</label>
                <InputText v-model="addIp" placeholder="IP" />
              </div>
              <div class="field-stack">
                <label class="field-label">Port</label>
                <InputText v-model="addPort" placeholder="Port" />
              </div>
              <div class="field-stack">
                <label class="field-label">Display ID</label>
                <InputText v-model="addDisplayId" placeholder="Display ID" />
              </div>
              <div class="field-stack">
                <label class="field-label">Agent ID</label>
                <Select
                  v-model="addAgentId"
                  :options="detectedAgentOptions"
                  option-label="label"
                  option-value="value"
                  editable
                  placeholder="Select or type Agent ID"
                />
              </div>
              <div class="field-stack">
                <label class="field-label">Protocol</label>
                <Select
                  v-model="addProtocol"
                  :options="protocolOptions"
                  option-label="label"
                  option-value="value"
                />
              </div>
              <Button
                label="Auto Detect Agent"
                icon="pi pi-compass"
                severity="secondary"
                class="detect-connection-btn"
                @click="autoDetectAddAgentId"
              />
              <Button
                label="Detect Connection"
                icon="pi pi-search"
                severity="secondary"
                class="detect-connection-btn"
                @click="autoProbeAddDraft"
              />
            </div>

            <div class="toolbar">
              <InputText
                v-model="deviceSearch"
                placeholder="Search by name, IP, or ID"
                class="toolbar-input"
              />
              <Select
                v-model="siteFilter"
                :options="siteFilterItems"
                option-label="label"
                option-value="value"
                class="toolbar-select"
              />
              <Select
                v-model="cityFilter"
                :options="cityFilterItems"
                option-label="label"
                option-value="value"
                class="toolbar-select"
              />
              <Select
                v-model="statusFilter"
                :options="statusFilterOptions"
                option-label="label"
                option-value="value"
                class="toolbar-select"
              />
              <Button
                label="Clear Filters"
                severity="secondary"
                outlined
                @click="clearFilters"
              />
              <Button
                label="Refresh All Status"
                icon="pi pi-refresh"
                @click="refreshAllDevices"
              />
              <Button
                :label="`Delete Selected (${selectedDeviceCount})`"
                icon="pi pi-trash"
                severity="danger"
                outlined
                :disabled="selectedDeviceCount === 0"
                @click="requestDeleteSelectedDevices"
              />
            </div>

            <div class="legend">
              <span class="legend-item"
                ><Tag value="Online" severity="success"
              /></span>
              <span class="legend-item"
                ><Tag value="Offline" severity="danger"
              /></span>
              <span class="legend-item"
                ><Tag value="Checking" severity="warn"
              /></span>
              <span class="legend-item"
                ><Tag value="Unknown" severity="secondary"
              /></span>
            </div>

            <DataTable
              v-model:selection="selectedDeviceRows"
              :value="sortedFilteredDevices"
              data-key="id"
              selection-mode="multiple"
              striped-rows
              class="device-table-prime"
              size="small"
            >
              <template #empty>No devices match current filters.</template>

              <Column selection-mode="multiple" header-style="width: 2.8rem" />

              <Column>
                <template #header>
                  <Button
                    text
                    class="sort-button"
                    @click="toggleSort('name')"
                    :label="`Name ${sortLabel('name')}`"
                  />
                </template>
                <template #body="{ data }">{{ data.name }}</template>
              </Column>

              <Column header="IP">
                <template #body="{ data }">
                  {{ data.ip }}:{{ data.port }} (ID {{ data.displayId }})
                </template>
              </Column>

              <Column header="Location">
                <template #body="{ data }">{{ data.city || '-' }}</template>
              </Column>

              <Column header="Protocol">
                <template #body="{ data }">{{
                  protocolLabel(data.protocol)
                }}</template>
              </Column>

              <Column header="Agent ID">
                <template #body="{ data }">
                  <Tag
                    :value="agentStatusLabelForDevice(data)"
                    :severity="agentStatusSeverityForDevice(data)"
                  />
                </template>
              </Column>

              <Column>
                <template #header>
                  <Button
                    text
                    class="sort-button"
                    @click="toggleSort('status')"
                    :label="`Status ${sortLabel('status')}`"
                  />
                </template>
                <template #body="{ data }">
                  <Tag
                    :value="data.status"
                    :severity="statusSeverity(data.status)"
                  />
                </template>
              </Column>

              <Column>
                <template #header>
                  <Button
                    text
                    class="sort-button"
                    @click="toggleSort('lastChecked')"
                    :label="`Last Check ${sortLabel('lastChecked')}`"
                  />
                </template>
                <template #body="{ data }">{{ data.lastChecked }}</template>
              </Column>

              <Column header="Action">
                <template #body="{ data }">
                  <div class="row-actions">
                    <Button
                      label="Test"
                      size="small"
                      severity="secondary"
                      @click="checkDevice(data)"
                    />
                    <Button
                      label="Open"
                      size="small"
                      severity="info"
                      outlined
                      @click="openDevice(data)"
                    />
                    <Button
                      label="Delete"
                      size="small"
                      severity="danger"
                      outlined
                      @click="requestDeleteDevice(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>
      </section>

      <section v-else-if="currentView === 'agents'" class="panel">
        <Card>
          <template #title>Explore Agents</template>
          <template #content>
            <div class="agent-status-panel">
              <div class="agent-status-header">
                <strong>Agents</strong>
                <span>Last update: {{ agentsLastUpdatedAt }}</span>
                <Button
                  label="Refresh Agent Status"
                  icon="pi pi-refresh"
                  severity="secondary"
                  outlined
                  :loading="isAgentRefreshBusy"
                  :disabled="isAgentRefreshBusy"
                  @click="refreshAgentStatusManual"
                />
              </div>

              <div v-if="trackedAgentRows.length" class="agent-status-list">
                <div
                  v-for="agent in trackedAgentRows"
                  :key="agent.agentId"
                  class="agent-status-item"
                >
                  <span class="agent-status-id">{{ agent.agentId }}</span>
                  <Tag :value="agent.status" :severity="agent.severity" />
                  <span class="agent-status-time">{{
                    agent.lastSeenLabel
                  }}</span>
                </div>
              </div>
              <p v-else class="feedback">No Agent ID assigned yet.</p>
            </div>
          </template>
        </Card>
      </section>

      <section v-else-if="currentView === 'device'" class="panel detail-grid">
        <template v-if="selectedDevice">
          <Card>
            <template #title>Connection</template>
            <template #content>
              <p class="card-help">
                Edit selected device settings and run connection/power actions.
              </p>
              <div class="form-grid">
                <div class="field-stack">
                  <label class="field-label">Device Name</label>
                  <InputText v-model="selectedDevice.name" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Site</label>
                  <InputText v-model="selectedDevice.site" placeholder="Site" />
                </div>
                <div class="field-stack">
                  <label class="field-label">City</label>
                  <InputText v-model="selectedDevice.city" placeholder="City" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Zone</label>
                  <InputText v-model="selectedDevice.zone" placeholder="Zone" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Area</label>
                  <InputText v-model="selectedDevice.area" placeholder="Area" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Description</label>
                  <InputText
                    v-model="selectedDevice.description"
                    placeholder="Description"
                  />
                </div>
                <div class="field-stack">
                  <label class="field-label">IP</label>
                  <InputText v-model="selectedDevice.ip" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Port</label>
                  <InputText v-model="selectedDevice.port" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Display ID</label>
                  <InputText v-model="selectedDevice.displayId" />
                </div>
                <div class="field-stack">
                  <label class="field-label">Agent ID</label>
                  <InputText
                    v-model="selectedDevice.agentId"
                    placeholder="Agent ID"
                  />
                </div>
                <div class="field-stack">
                  <label class="field-label">Protocol</label>
                  <Select
                    v-model="selectedDevice.protocol"
                    :options="protocolOptions"
                    option-label="label"
                    option-value="value"
                  />
                </div>
                <Button label="Save Changes" @click="saveSelectedDevice" />
              </div>
              <div class="toolbar">
                <Button
                  label="Test Connection"
                  icon="pi pi-wifi"
                  :loading="isDeviceTestBusy"
                  :disabled="isPowerBusy || isMdcBusy"
                  @click="runSelectedDeviceTest"
                />
                <Button
                  label="Power ON"
                  severity="success"
                  outlined
                  :loading="isPowerBusy"
                  :disabled="isDeviceTestBusy || isMdcBusy"
                  @click="requestPowerAction('on')"
                />
                <Button
                  label="Power OFF"
                  severity="danger"
                  outlined
                  :loading="isPowerBusy"
                  :disabled="isDeviceTestBusy || isMdcBusy"
                  @click="requestPowerAction('off')"
                />
                <Button
                  label="Back to Dashboard"
                  severity="secondary"
                  text
                  @click="currentView = 'dashboard'"
                />
              </div>
              <p class="feedback">{{ selectedDevice.lastFeedback }}</p>
            </template>
          </Card>

          <Card>
            <template #title>MDC CLI</template>
            <template #content>
              <p class="card-help">
                Run MDC commands, quick actions, and optional argument
                overrides.
              </p>
              <div class="mdc-level-grid">
                <div class="mdc-level-card">
                  <div class="mdc-level-header">
                    <span>Volume</span>
                    <strong>{{ volumeLevel }}</strong>
                  </div>
                  <Slider v-model="volumeLevel" :min="0" :max="100" :step="1" />
                  <Button
                    label="Set Volume"
                    icon="pi pi-play"
                    :loading="isMdcBusy"
                    :disabled="isDeviceTestBusy || isPowerBusy"
                    @click="setVolumeFromSlider"
                  />
                </div>

                <div class="mdc-level-card">
                  <div class="mdc-level-header">
                    <span>Brightness</span>
                    <strong>{{ brightnessLevel }}</strong>
                  </div>
                  <Slider
                    v-model="brightnessLevel"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                  <Button
                    label="Set Brightness"
                    icon="pi pi-play"
                    :loading="isMdcBusy"
                    :disabled="isDeviceTestBusy || isPowerBusy"
                    @click="setBrightnessFromSlider"
                  />
                </div>
              </div>

              <div class="quick-actions-row">
                <Button
                  label="Get Status"
                  icon="pi pi-info-circle"
                  severity="secondary"
                  outlined
                  :loading="isMdcBusy"
                  :disabled="isDeviceTestBusy || isPowerBusy"
                  @click="
                    runMdcQuickAction({ command: 'status', operation: 'get' })
                  "
                />
                <Button
                  label="Mute ON"
                  severity="secondary"
                  outlined
                  :loading="isMdcBusy"
                  :disabled="isDeviceTestBusy || isPowerBusy"
                  @click="runMuteQuickAction(true)"
                />
                <Button
                  label="Mute OFF"
                  severity="secondary"
                  outlined
                  :loading="isMdcBusy"
                  :disabled="isDeviceTestBusy || isPowerBusy"
                  @click="runMuteQuickAction(false)"
                />
              </div>

              <div class="mdc-cli-stack">
                <div class="form-grid mdc-cli-controls">
                  <div class="mdc-command-select-wrap">
                    <Select
                      v-model="selectedMdcCommand"
                      :options="mdcCommandOptions"
                      option-label="label"
                      option-value="name"
                      class="mdc-command-select"
                    />
                    <Button
                      icon="pi pi-info-circle"
                      class="mdc-info-btn"
                      severity="secondary"
                      outlined
                      aria-label="Command information"
                      :disabled="!selectedMdcCommand"
                      @click="openCommandInfo"
                    />
                  </div>
                  <Select
                    v-model="mdcOperation"
                    :options="mdcOperationOptions"
                  />
                  <Button
                    label="Run CLI Command"
                    :loading="isMdcBusy"
                    :disabled="isDeviceTestBusy || isPowerBusy"
                    @click="runMdcCommand"
                  />
                </div>
                <p class="feedback">
                  Final args:
                  {{
                    effectiveMdcArgs.length
                      ? effectiveMdcArgs.join(', ')
                      : '(none)'
                  }}
                </p>
                <p v-if="selectedCommandMeta" class="feedback">
                  {{ mdcCommandLabel(selectedCommandMeta.name) }} | GET:
                  {{ selectedCommandMeta.supports_get ? 'yes' : 'no' }} | SET:
                  {{ selectedCommandMeta.supports_set ? 'yes' : 'no' }}
                </p>

                <div v-if="selectedMdcFields.length" class="mdc-args-panel">
                  <div class="mdc-args-title">Arguments</div>
                  <div
                    v-for="field in selectedMdcFields"
                    :key="field.name"
                    class="mdc-arg-row"
                  >
                    <div class="mdc-arg-label">
                      <strong>{{ formatFieldLabel(field.name) }}</strong>
                    </div>

                    <div class="mdc-arg-inputs">
                      <template
                        v-if="Array.isArray(field.enum) && field.enum.length"
                      >
                        <Select
                          v-model="mdcFieldValues[field.name]"
                          :options="field.enum"
                          placeholder="Select"
                          class="mdc-arg-select"
                        />
                        <span class="mdc-arg-or">Custom value:</span>
                        <InputText
                          v-model="mdcFieldValues[field.name]"
                          placeholder="Value"
                          class="mdc-arg-manual"
                        />
                      </template>

                      <template v-else>
                        <InputText
                          v-model="mdcFieldValues[field.name]"
                          :placeholder="
                            field.range
                              ? `${field.range.min}-${field.range.max}`
                              : 'Value'
                          "
                          class="mdc-arg-manual"
                        />
                      </template>
                    </div>
                  </div>
                </div>

                <div class="mdc-manual-panel">
                  <div class="mdc-manual-title">Manual Override (optional)</div>
                  <div class="mdc-manual-row">
                    <span>Values:</span>
                    <InputText
                      v-model="mdcArgsText"
                      placeholder="comma-separated values"
                      class="mdc-manual-input"
                    />
                  </div>
                </div>
              </div>

              <Dialog
                v-model:visible="isCommandInfoOpen"
                modal
                :draggable="false"
                header="MDC Command Information"
                :style="{ width: 'min(720px, 92vw)' }"
              >
                <div class="mdc-info-dialog">
                  <p>
                    <strong>Command:</strong>
                    {{
                      selectedMdcCommand
                        ? mdcCommandLabel(selectedMdcCommand)
                        : '-'
                    }}
                  </p>
                  <p><strong>Description:</strong> {{ selectedCommandHelp }}</p>
                  <div v-if="selectedCommandNotes.length">
                    <strong>Notes:</strong>
                    <ul class="mdc-info-fields">
                      <li
                        v-for="(note, index) in selectedCommandNotes"
                        :key="`note-${selectedMdcCommand}-${index}`"
                      >
                        {{ note }}
                      </li>
                    </ul>
                  </div>
                  <div v-if="selectedCommandFormats.length">
                    <strong>Format Tips:</strong>
                    <ul class="mdc-info-fields">
                      <li
                        v-for="(tip, index) in selectedCommandFormats"
                        :key="`tip-${selectedMdcCommand}-${index}`"
                      >
                        {{ tip }}
                      </li>
                    </ul>
                  </div>
                  <p>
                    <strong>Supports:</strong>
                    GET {{ selectedCommandMeta?.supports_get ? 'yes' : 'no' }} |
                    SET {{ selectedCommandMeta?.supports_set ? 'yes' : 'no' }}
                  </p>
                  <div>
                    <strong>Arguments:</strong>
                    <ul v-if="selectedMdcFields.length" class="mdc-info-fields">
                      <li
                        v-for="field in selectedMdcFields"
                        :key="`help-${field.name}`"
                      >
                        <strong>{{ formatFieldLabel(field.name) }}</strong>
                        <span
                          v-if="Array.isArray(field.enum) && field.enum.length"
                        >
                          : {{ field.enum.join(' | ') }}
                        </span>
                        <span v-else-if="field.range">
                          : {{ field.range.min }} - {{ field.range.max }}
                        </span>
                        <span v-else>: value</span>
                      </li>
                    </ul>
                    <p v-else class="feedback">No arguments required.</p>
                  </div>
                  <p><strong>Example:</strong> {{ selectedCommandExample }}</p>
                </div>
              </Dialog>
            </template>
          </Card>

          <Card class="logs">
            <template #title>
              <div
                style="
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 0.75rem;
                "
              >
                <span>Logs</span>
                <div style="display: flex; align-items: center; gap: 0.5rem">
                  <Button
                    label="Save Logs CSV"
                    icon="pi pi-download"
                    size="small"
                    severity="secondary"
                    outlined
                    :disabled="commandLogs.length === 0"
                    @click="saveLogsCsv"
                  />
                  <Button
                    label="Copy Last Log"
                    icon="pi pi-copy"
                    size="small"
                    severity="secondary"
                    outlined
                    :disabled="commandLogs.length === 0"
                    @click="copyLastLog"
                  />
                  <Button
                    label="Clear Logs"
                    icon="pi pi-trash"
                    size="small"
                    severity="danger"
                    outlined
                    :disabled="commandLogs.length === 0"
                    @click="clearLogs"
                  />
                </div>
              </div>
            </template>
            <template #content>
              <p class="card-help">
                Latest command output and troubleshooting messages.
              </p>
              <pre>{{ commandLogs.join('\n') }}</pre>
            </template>
          </Card>
        </template>

        <Card v-else>
          <template #title>Device Control</template>
          <template #content>
            <p class="card-help">
              No device selected yet. Add or import a device from Dashboard,
              then click Open to control it.
            </p>
            <div class="toolbar">
              <Button
                label="Go to Dashboard"
                severity="secondary"
                text
                @click="currentView = 'dashboard'"
              />
            </div>
          </template>
        </Card>
      </section>
    </section>

    <div class="status-row">
      <div class="status-log-bar" :title="appStatus">
        Status log: "{{ appStatus }}"
      </div>

      <Button
        icon="pi pi-arrow-up"
        class="scroll-top-btn"
        rounded
        aria-label="Scroll to top"
        @click="scrollToTop"
      />
    </div>
  </main>
</template>
