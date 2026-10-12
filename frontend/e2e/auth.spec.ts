import { test, expect } from '@playwright/test';

test.describe('Bharat FoodSafe — Authentication & Role-Based Navigation Journeys', () => {
  test.beforeEach(async ({ page }) => {
    // Start each test from a clean session state
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();
  });

  test('Journey 1: Staff login, staff dashboard assertions, sign-out and return to login', async ({ page }) => {
    // 1. Select Staff/Manager tab (active by default)
    await page.getByRole('button', { name: 'Kitchen Staff / Manager' }).click();

    // 2. Fill valid staff credentials (Demo Kitchen Staff)
    await page.getByLabel('Mobile Phone Number').fill('9876543210');
    await page.getByLabel('Security PIN').fill('1234');

    // 3. Submit login
    await page.getByRole('button', { name: 'Sign In with Phone & PIN' }).click();

    // 4. Assert navigation to Staff Dashboard
    await expect(page).toHaveURL(/\/staff\/dashboard/);
    await expect(page.getByText('Active Staff Session')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Welcome, Demo Kitchen Staff' })).toBeVisible();
    await expect(page.getByText('Kitchen Staff Task Execution Portal')).toBeVisible();
    await expect(page.getByText('User ID:')).toBeVisible();
    await expect(page.getByText('Tenant ID:')).toBeVisible();

    // 5. Sign out and verify return to /login
    await page.getByRole('button', { name: 'Sign Out' }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();
  });

  test('Journey 2: Platform administrator login, global-scope assertions and sign-out', async ({ page }) => {
    // 1. Switch to Platform Admin tab
    await page.getByRole('button', { name: 'Platform Admin' }).click();
    await expect(page.getByLabel('Admin Email Address')).toBeVisible();

    // 2. Fill valid platform admin credentials
    await page.getByLabel('Admin Email Address').fill('admin@bharatfoodsafe.io');
    await page.getByLabel('Password').fill('AdminPass123!');

    // 3. Submit admin login
    await page.getByRole('button', { name: 'Sign In as Admin' }).click();

    // 4. Assert navigation to Admin Dashboard
    await expect(page).toHaveURL(/\/admin\/dashboard/);
    await expect(page.getByText('Platform Admin Session')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Platform Administration: Demo Platform Admin' })
    ).toBeVisible();
    await expect(
      page.getByText('System Multi-Tenant Management & Rule Engine Config')
    ).toBeVisible();
    await expect(page.getByText('Tenant Scope: Global Admin')).toBeVisible();

    // 5. Sign out and verify session termination
    await page.getByRole('button', { name: 'Sign Out' }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();
  });

  test('Journey 3: Manager-role authorization and manager dashboard access', async ({ page }) => {
    // 1. Log in with the shared STAFF/MANAGER account (9876543210)
    await page.getByRole('button', { name: 'Kitchen Staff / Manager' }).click();
    await page.getByLabel('Mobile Phone Number').fill('9876543210');
    await page.getByLabel('Security PIN').fill('1234');
    await page.getByRole('button', { name: 'Sign In with Phone & PIN' }).click();

    // 2. Default login redirect routes to /staff/dashboard due to priority order
    await expect(page).toHaveURL(/\/staff\/dashboard/);

    // 3. Navigate directly to /manager/dashboard within the active session to verify MANAGER authorization
    await page.evaluate(() => {
      window.history.pushState({}, '', '/manager/dashboard');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    // 4. Assert that Manager Dashboard renders successfully with no "Access Denied"
    await expect(page).toHaveURL(/\/manager\/dashboard/);
    await expect(page.getByText('Active Manager Session')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Manager Portal: Demo Kitchen Staff' })
    ).toBeVisible();
    await expect(
      page.getByText('Outlet Operational Compliance & Incident Resolution Overview')
    ).toBeVisible();
    await expect(page.getByText('Access Denied')).not.toBeVisible();

    // 5. Sign out from manager view
    await page.getByRole('button', { name: 'Sign Out' }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test('Journey 4: Form validation and invalid staff/admin credentials handling', async ({ page }) => {
    // --- A. Staff Client-side Form Validation ---
    await page.getByLabel('Mobile Phone Number').fill('123'); // Invalid phone length
    await page.getByLabel('Security PIN').fill('1234');
    await page.getByRole('button', { name: 'Sign In with Phone & PIN' }).click();
    await expect(
      page.getByText('Please enter a valid 10-digit mobile phone number.')
    ).toBeVisible();

    await page.getByLabel('Mobile Phone Number').fill('9876543210');
    await page.getByLabel('Security PIN').fill('12'); // Too short PIN (<4 digits)
    await page.getByRole('button', { name: 'Sign In with Phone & PIN' }).click();
    await expect(
      page.getByText('Please enter a valid 4 to 6 digit security PIN.')
    ).toBeVisible();

    // --- B. Staff Server-side 401 Rejection ---
    await page.getByLabel('Mobile Phone Number').fill('9876543210');
    await page.getByLabel('Security PIN').fill('9999'); // Incorrect PIN
    await page.getByRole('button', { name: 'Sign In with Phone & PIN' }).click();
    await expect(page.getByText('Invalid phone number or PIN.')).toBeVisible();

    // --- C. Admin Client-side Form Validation ---
    await page.getByRole('button', { name: 'Platform Admin' }).click();
    const adminEmail = page.getByLabel('Admin Email Address');
    const adminPassword = page.getByLabel('Password');

    // 1. Browser HTML5 constraint validation on invalid email
    await adminEmail.fill('notanemail');
    await adminPassword.fill('123456');
    await page.getByRole('button', { name: 'Sign In as Admin' }).click();
    const isEmailValid = await adminEmail.evaluate((el: HTMLInputElement) => el.checkValidity());
    expect(isEmailValid).toBe(false);

    // 2. React form validation on short password (< 6 chars)
    await adminEmail.fill('admin@bharatfoodsafe.io');
    await adminPassword.fill('123');
    await page.getByRole('button', { name: 'Sign In as Admin' }).click();
    await expect(page.getByText('Please enter your admin password.')).toBeVisible();

    // --- D. Admin Server-side 401 Rejection ---
    await adminEmail.fill('admin@bharatfoodsafe.io');
    await adminPassword.fill('WrongPassword123!');
    await page.getByRole('button', { name: 'Sign In as Admin' }).click();
    await expect(page.getByText('Invalid email address or password.')).toBeVisible();
  });

  test('Journey 5: Unauthenticated direct access to protected routes and root-route behavior', async ({ page }) => {
    // 1. Direct access to /staff/dashboard without authentication redirects to /login
    await page.goto('/staff/dashboard');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();

    // 2. Direct access to /manager/dashboard without authentication redirects to /login
    await page.goto('/manager/dashboard');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();

    // 3. Direct access to /admin/dashboard without authentication redirects to /login
    await page.goto('/admin/dashboard');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();

    // 4. Direct access to root / without authentication redirects to /login
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Bharat FoodSafe' })).toBeVisible();
  });
});
