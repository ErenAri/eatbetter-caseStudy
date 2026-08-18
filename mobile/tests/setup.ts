// React Native Testing Library v14 performs asynchronous renderer setup.
jest.setTimeout(15000);
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
